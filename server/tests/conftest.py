from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

# Required env BEFORE app imports
os.environ.setdefault("API_TOKEN", "test-token-1234567890")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-deepseek-key-xxxxxx")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("SCHEDULER_ENABLED", "false")  # tests drive notifier.tick() manually
# Isolate tests from a real server/.env that may contain Telegram secrets.
# Force-empty (override the .env file) so the bot is disabled by default in tests.
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["PUBLIC_BASE_URL"] = ""
os.environ["TELEGRAM_WEBHOOK_SECRET"] = ""
os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = ""
# Pin extraction tunables so tests are deterministic regardless of dev's .env
os.environ["EXTRACTION_MAX_ATTEMPTS"] = "3"
os.environ["EXTRACTION_VERIFY_ENABLED"] = "true"
os.environ["EXTRACTION_VERIFY_MODEL"] = "deepseek-v4-flash"
os.environ["EXTRACTION_TOKEN_BUDGET_PER_INGEST"] = "16000"
os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-pro"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import db as db_module
from app.db import Base
from app.deps import set_llm_override
from app.llm.adapter import LLMCallResult
from app.services.notifier import reset_broker_for_tests


class StubLLM:
    """Scriptable LLM stub. Each call pops the next scripted response."""

    def __init__(self) -> None:
        self.responses: list[LLMCallResult | Exception] = []
        self.calls: list[dict[str, Any]] = []

    def push(
        self,
        raw_text: str,
        *,
        model: str = "stub-model",
        prompt_tokens: int = 50,
        completion_tokens: int = 50,
        latency_ms: int = 10,
    ) -> None:
        self.responses.append(
            LLMCallResult(
                raw_text=raw_text,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
            )
        )

    def push_error(self, exc: Exception) -> None:
        self.responses.append(exc)

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
    ) -> LLMCallResult:
        self.calls.append({"messages": messages, "model": model})
        if not self.responses:
            raise RuntimeError("StubLLM exhausted: no more scripted responses")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


@pytest_asyncio.fixture
async def stub_llm() -> AsyncIterator[StubLLM]:
    stub = StubLLM()
    set_llm_override(stub)
    try:
        yield stub
    finally:
        set_llm_override(None)


@pytest_asyncio.fixture
async def test_db() -> AsyncIterator[None]:
    """Replace the global engine with an in-memory SQLite for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = factory
    reset_broker_for_tests()
    try:
        yield
    finally:
        db_module._engine = original_engine
        db_module._session_factory = original_factory
        await engine.dispose()
        reset_broker_for_tests()


@asynccontextmanager
async def _lifespan_runner(app):
    async with app.router.lifespan_context(app):
        yield


@pytest_asyncio.fixture
async def client(test_db: None, stub_llm: StubLLM) -> AsyncIterator[AsyncClient]:
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer test-token-1234567890"},
        ) as ac,
        _lifespan_runner(app),
    ):
        yield ac


@pytest.fixture
def settings():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    return get_settings()
