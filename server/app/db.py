from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


# SQLite doesn't enforce foreign keys by default (so ON DELETE SET NULL and
# CASCADE silently no-op). Enable it on every new connection.
@event.listens_for(Engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, _connection_record):
    try:
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    except Exception:  # noqa: BLE001
        pass  # non-SQLite drivers will just ignore this


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Store tz-aware datetimes as UTC; read back as UTC tz-aware.

    SQLite has no native timezone support — `DateTime(timezone=True)` on SQLite
    silently drops tz info. This decorator normalizes everything to UTC on write
    and re-attaches UTC on read, so downstream code can rely on tz-aware datetimes.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # type: ignore[override]
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "naive datetime not allowed; convert to tz-aware before persisting"
            )
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):  # type: ignore[override]
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def _make_engine() -> tuple:
    settings = get_settings()
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if not settings.DATABASE_URL.startswith("sqlite"):
        kwargs["pool_size"] = 1
        kwargs["max_overflow"] = 2
    engine = create_async_engine(settings.DATABASE_URL, **kwargs)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, session_factory


_engine, _session_factory = _make_engine()


def get_engine():
    return _engine


def get_session_factory():
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def reset_engine_for_tests(url: str) -> None:
    """For tests: swap the engine to point at an in-memory or temp DB."""
    global _engine, _session_factory
    await _engine.dispose()
    _engine = create_async_engine(url, future=True, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
