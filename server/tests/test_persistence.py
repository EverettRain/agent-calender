"""Regression tests for issues found during real DeepSeek integration testing."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.db import get_session_factory
from app.models import Reminder
from app.services.extractor import ExtractorService


def _t_shanghai(hours: int = 24) -> str:
    """Return an ISO string in Asia/Shanghai (+08:00) timezone."""
    tz = timezone(timedelta(hours=8))
    return (datetime.now(UTC).astimezone(tz) + timedelta(hours=hours)).isoformat()


def _gen(items) -> str:
    return json.dumps({"reminders": items})


def _verify(passed: bool, issues=None) -> str:
    return json.dumps({"pass": passed, "issues": issues or []})


@pytest.mark.asyncio
async def test_target_at_preserves_timezone_through_roundtrip(test_db, stub_llm):
    """LLM returns +08:00 → store → read back must still be tz-aware (UTC)."""
    settings = get_settings()
    target_str = _t_shanghai(48)
    stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": target_str}]))
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()
    rid = result.reminders[0].id

    # Read back from a fresh session
    async with factory() as session:
        fresh = await session.get(Reminder, rid)

    assert fresh is not None
    assert fresh.target_at.tzinfo is not None, "target_at lost timezone on roundtrip"
    assert fresh.target_at.utcoffset() == timedelta(0), "should be normalized to UTC"
    # Same instant in time as what LLM sent (compare in UTC)
    expected_utc = datetime.fromisoformat(target_str).astimezone(UTC)
    assert fresh.target_at == expected_utc


@pytest.mark.asyncio
async def test_created_at_is_tz_aware_on_read(test_db, stub_llm):
    settings = get_settings()
    stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": _t_shanghai()}]))
    stub_llm.push(_verify(True))
    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()
    rid = result.reminders[0].id

    async with factory() as session:
        fresh = await session.get(Reminder, rid)
    assert fresh is not None
    assert fresh.created_at.tzinfo is not None
    assert fresh.updated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_llm_empty_offsets_falls_back_to_defaults(test_db, stub_llm):
    """If the LLM lazily returns [] (no reminders), service must apply defaults."""
    settings = get_settings()
    stub_llm.push(
        _gen(
            [
                {
                    "kind": "event",
                    "title": "组会",
                    "target_at": _t_shanghai(),
                    "advance_reminders_minutes": [],
                },
                {
                    "kind": "deadline",
                    "title": "交报告",
                    "target_at": _t_shanghai(72),
                    "advance_reminders_minutes": [],
                },
            ]
        )
    )
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    by_kind = {r.kind: r for r in result.reminders}
    assert by_kind["event"].advance_reminders_minutes == [0]
    assert by_kind["deadline"].advance_reminders_minutes == [60, 1440]


@pytest.mark.asyncio
async def test_manual_create_empty_offsets_stays_silent(client):
    """For MANUAL create via PUT/POST, [] explicitly means silent (no fallback).

    Different from LLM extraction: manual user input is precise, LLM output is fuzzy.
    """
    r = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "silent event",
            "target_at": _t_shanghai(),
            "advance_reminders_minutes": [],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["advance_reminders_minutes"] == []
