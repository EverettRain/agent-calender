from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid_str() -> str:
    return str(uuid.uuid4())


class ReminderKind(str, Enum):
    EVENT = "event"
    DEADLINE = "deadline"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    PENDING_REVIEW = "pending_review"
    NOTIFIED = "notified"
    DONE = "done"
    CANCELLED = "cancelled"


class AttemptStage(str, Enum):
    GENERATE = "generate"
    VERIFY = "verify"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, index=True
    )
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    participants: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    advance_reminders_minutes: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list
    )
    fired_offsets: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReminderStatus.PENDING.value, index=True)

    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    llm_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Logical grouping UUID, not a strict FK (one group → many attempts → many reminders)
    extraction_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ExtractionAttempt(Base):
    __tablename__ = "extraction_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    extraction_group_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    verify_pass: Mapped[bool | None] = mapped_column(nullable=True)
    verify_issues: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, nullable=False)
