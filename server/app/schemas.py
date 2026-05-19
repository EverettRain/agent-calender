from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import ReminderKind, ReminderStatus

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalize_offsets(values: list[int]) -> list[int]:
    cleaned = sorted({int(v) for v in values if v is not None})
    if any(v < 0 for v in cleaned):
        raise ValueError("advance_reminders_minutes must be non-negative")
    return cleaned


def _validate_color(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not HEX_COLOR_RE.match(v):
        raise ValueError("color must be a 7-char hex string like '#a3b1c5'")
    return v.lower()


# ===== LLM-produced shapes (extractor) =====


class ReminderDraft(BaseModel):
    """LLM-produced draft, validated before persistence."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["event", "deadline"]
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    target_at: datetime
    end_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=1)
    location: str | None = Field(None, max_length=200)
    participants: list[str] = Field(default_factory=list)
    advance_reminders_minutes: list[int] | None = None

    @field_validator("participants")
    @classmethod
    def _dedupe_participants(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for p in v:
            p = p.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out

    @field_validator("advance_reminders_minutes")
    @classmethod
    def _normalize_offsets_field(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        return _normalize_offsets(v)

    @model_validator(mode="after")
    def _enforce_kind_rules(self) -> ReminderDraft:
        if self.kind == "deadline" and (
            self.end_at is not None or self.duration_minutes is not None
        ):
            raise ValueError("deadline must not have end_at or duration_minutes")
        if self.end_at is not None and self.target_at and self.end_at <= self.target_at:
            raise ValueError("end_at must be after target_at")
        return self


class GenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminders: list[ReminderDraft] = Field(..., min_length=1, max_length=20)


class VerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_: bool = Field(..., alias="pass")
    issues: list[str] = Field(default_factory=list)


# ===== Tag / Group DTOs =====


class TagBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    color: str | None = Field(None, max_length=16)

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_color(v)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=64)
    color: str | None = None

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_color(v)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str | None
    created_at: datetime


class GroupBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    color: str | None = Field(None, max_length=16)
    position: int = 0

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_color(v)


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=64)
    color: str | None = None
    position: int | None = None

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_color(v)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str | None
    position: int
    created_at: datetime


# ===== Reminder DTOs =====


class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    source_channel: str = Field(default="api", max_length=32)


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: Literal["event", "deadline"]
    title: str
    description: str | None
    target_at: datetime
    end_at: datetime | None
    duration_minutes: int | None
    location: str | None
    participants: list[str]
    advance_reminders_minutes: list[int]
    fired_offsets: list[int]
    status: str
    source_text: str
    source_channel: str
    llm_model: str | None
    extraction_group_id: str | None
    group_id: str | None
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime


class IngestResponse(BaseModel):
    extraction_group_id: str
    status: Literal["success", "pending_review"]
    reminders: list[ReminderOut]
    attempts: int
    total_tokens: int


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    target_at: datetime | None = None
    end_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=1)
    location: str | None = Field(None, max_length=200)
    participants: list[str] | None = None
    advance_reminders_minutes: list[int] | None = None
    status: Literal["pending", "pending_review", "notified", "done", "cancelled"] | None = None
    group_id: str | None = None  # null literal explicitly = move to Inbox
    tag_ids: list[str] | None = None  # null = no change; [] = clear all

    @field_validator("advance_reminders_minutes")
    @classmethod
    def _norm(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        return _normalize_offsets(v)


class ManualReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["event", "deadline"]
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    target_at: datetime
    end_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=1)
    location: str | None = Field(None, max_length=200)
    participants: list[str] = Field(default_factory=list)
    advance_reminders_minutes: list[int] | None = None
    group_id: str | None = None
    tag_ids: list[str] = Field(default_factory=list)

    @field_validator("advance_reminders_minutes")
    @classmethod
    def _norm(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        return _normalize_offsets(v)


class ExtractionAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    extraction_group_id: str
    attempt_no: int
    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    result_json: str | None
    verify_pass: bool | None
    verify_issues: list[str] | None
    error: str | None
    created_at: datetime


class ExtractionGroupOut(BaseModel):
    extraction_group_id: str
    source_text: str
    attempts: list[ExtractionAttemptOut]
    reminders: list[ReminderOut]


__all__ = [
    "ReminderDraft",
    "GenerateResponse",
    "VerifyResponse",
    "IngestRequest",
    "IngestResponse",
    "ReminderOut",
    "ReminderUpdate",
    "ManualReminderCreate",
    "ExtractionAttemptOut",
    "ExtractionGroupOut",
    "ReminderKind",
    "ReminderStatus",
    "TagOut",
    "TagCreate",
    "TagUpdate",
    "GroupOut",
    "GroupCreate",
    "GroupUpdate",
]
