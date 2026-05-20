from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import extractions, groups, health, ingest, reminders, stream, tags
from app.api import settings as settings_api
from app.api import telegram as telegram_api
from app.config import get_settings
from app.db import Base, get_engine, get_session_factory
from app.deps import get_llm
from app.services.extractor import ExtractorService
from app.services.notifier import NotificationService, get_broker
from app.services.telegram_bot import start_telegram, stop_telegram


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.LOG_LEVEL)

    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite+aiosqlite:///"):
        rel = db_url.removeprefix("sqlite+aiosqlite:///").lstrip("./")
        # Skip ":memory:" and ensure parent dir exists for file-backed SQLite
        if rel and rel != ":memory:":
            Path(rel).parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler: AsyncIOScheduler | None = None
    if settings.SCHEDULER_ENABLED:
        notifier = NotificationService(get_broker(), get_session_factory())
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            notifier.tick,
            trigger="interval",
            seconds=settings.NOTIFY_TICK_SECONDS,
            id="notify_tick",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()

    # Telegram bot — no-op when token / public URL absent
    await start_telegram(
        settings=settings,
        session_factory=get_session_factory(),
        extractor_provider=lambda: ExtractorService(get_llm(), settings),
        broker=get_broker(),
    )

    try:
        yield
    finally:
        await stop_telegram()
        if scheduler is not None:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agent-Calendar",
        version="0.1.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=False,  # we use bearer tokens, not cookies
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=86400,
    )

    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(reminders.router)
    app.include_router(tags.router)
    app.include_router(groups.router)
    app.include_router(extractions.router)
    app.include_router(stream.router)
    app.include_router(settings_api.router)
    app.include_router(telegram_api.router)

    # Surface settings.TZ to dependents that look at the runtime TZ
    os.environ.setdefault("TZ", settings.TZ)
    return app


app = create_app()
