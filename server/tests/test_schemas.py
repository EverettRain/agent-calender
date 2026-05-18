from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas import GenerateResponse, ReminderDraft


def _t(offset_hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=offset_hours)).isoformat()


class TestReminderDraft:
    def test_event_basic(self):
        d = ReminderDraft.model_validate(
            {
                "kind": "event",
                "title": "组会",
                "target_at": _t(),
                "advance_reminders_minutes": [15, 0],
            }
        )
        assert d.advance_reminders_minutes == [0, 15]  # sorted dedupe

    def test_deadline_forbids_end_at(self):
        with pytest.raises(ValidationError, match="deadline must not have"):
            ReminderDraft.model_validate(
                {
                    "kind": "deadline",
                    "title": "交报告",
                    "target_at": _t(),
                    "end_at": _t(48),
                }
            )

    def test_deadline_forbids_duration(self):
        with pytest.raises(ValidationError, match="deadline must not have"):
            ReminderDraft.model_validate(
                {
                    "kind": "deadline",
                    "title": "交报告",
                    "target_at": _t(),
                    "duration_minutes": 30,
                }
            )

    def test_end_at_must_be_after_target(self):
        target = _t(48)
        end = _t(24)
        with pytest.raises(ValidationError, match="end_at must be after"):
            ReminderDraft.model_validate(
                {
                    "kind": "event",
                    "title": "x",
                    "target_at": target,
                    "end_at": end,
                }
            )

    def test_offsets_dedupe_sort(self):
        d = ReminderDraft.model_validate(
            {
                "kind": "deadline",
                "title": "x",
                "target_at": _t(),
                "advance_reminders_minutes": [60, 1440, 60, 0],
            }
        )
        assert d.advance_reminders_minutes == [0, 60, 1440]

    def test_offsets_reject_negative(self):
        with pytest.raises(ValidationError):
            ReminderDraft.model_validate(
                {
                    "kind": "deadline",
                    "title": "x",
                    "target_at": _t(),
                    "advance_reminders_minutes": [-1],
                }
            )

    def test_offsets_none_is_allowed(self):
        d = ReminderDraft.model_validate(
            {"kind": "event", "title": "x", "target_at": _t()}
        )
        assert d.advance_reminders_minutes is None

    def test_participants_dedupe(self):
        d = ReminderDraft.model_validate(
            {
                "kind": "event",
                "title": "x",
                "target_at": _t(),
                "participants": ["张三", "李四", "张三", " 王五 "],
            }
        )
        assert d.participants == ["张三", "李四", "王五"]


class TestGenerateResponse:
    def test_requires_at_least_one(self):
        with pytest.raises(ValidationError):
            GenerateResponse.model_validate({"reminders": []})

    def test_multiple_items_ok(self):
        r = GenerateResponse.model_validate(
            {
                "reminders": [
                    {"kind": "event", "title": "a", "target_at": _t()},
                    {"kind": "deadline", "title": "b", "target_at": _t(48)},
                ]
            }
        )
        assert len(r.reminders) == 2
        assert r.reminders[0].kind == "event"
        assert r.reminders[1].kind == "deadline"
