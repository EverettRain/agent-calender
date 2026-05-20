from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


# ====== Association table: Reminder <-> Tag (many-to-many) ======

reminder_tag_table = Table(
    "reminder_tags",
    Base.metadata,
    Column(
        "reminder_id",
        String(36),
        ForeignKey("reminders.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ====== Tag ======

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "#RRGGBB"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, nullable=False)


# ====== Group (a.k.a. list / project) ======

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, nullable=False)


class AppSettings(Base):
    """Single-row runtime settings. NULL fields fall back to env defaults.
    Always operated on via the id=1 row."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    generate_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verify_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verify_enabled: Mapped[bool | None] = mapped_column(nullable=True)
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ====== Reminder ======

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

    # User-managed organization: nullable group ("Inbox" when null) + free-form tags
    group_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=reminder_tag_table,
        lazy="selectin",
        order_by=Tag.name,
    )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ====== ExtractionAttempt ======

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
