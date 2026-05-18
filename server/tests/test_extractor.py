from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.models import ExtractionAttempt
from app.services.extractor import ExtractorService


def _t(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _gen(reminders_array) -> str:
    return json.dumps({"reminders": reminders_array})


def _verify(passed: bool, issues=None) -> str:
    return json.dumps({"pass": passed, "issues": issues or []})


@pytest.mark.asyncio
async def test_single_event_success(test_db, stub_llm):
    settings = get_settings()
    stub_llm.push(_gen([{"kind": "event", "title": "组会", "target_at": _t()}]))
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "明天开组会", "test")
        await session.commit()

    assert result.status == "success"
    assert len(result.reminders) == 1
    assert result.reminders[0].kind == "event"
    assert result.reminders[0].advance_reminders_minutes == [0]  # default
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_mixed_event_and_deadline(test_db, stub_llm):
    settings = get_settings()
    stub_llm.push(
        _gen(
            [
                {"kind": "event", "title": "组会", "target_at": _t()},
                {"kind": "deadline", "title": "报告", "target_at": _t(72)},
            ]
        )
    )
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "明天开组会，三天后交报告", "test")
        await session.commit()

    assert result.status == "success"
    assert len(result.reminders) == 2

    kinds = {r.kind for r in result.reminders}
    assert kinds == {"event", "deadline"}

    by_kind = {r.kind: r for r in result.reminders}
    # event default [0], deadline default [1440, 60] (env-driven)
    assert by_kind["event"].advance_reminders_minutes == [0]
    assert by_kind["deadline"].advance_reminders_minutes == [60, 1440]

    # All reminders share extraction_group_id
    gids = {r.extraction_group_id for r in result.reminders}
    assert len(gids) == 1
    assert result.extraction_group_id in gids


@pytest.mark.asyncio
async def test_verify_rejection_then_retry_success(test_db, stub_llm):
    settings = get_settings()
    stub_llm.push(_gen([{"kind": "event", "title": "wrong", "target_at": _t()}]))
    stub_llm.push(_verify(False, ["标题不对"]))
    stub_llm.push(_gen([{"kind": "event", "title": "组会", "target_at": _t()}]))
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "明天开组会", "test")
        await session.commit()

    assert result.status == "success"
    assert result.reminders[0].title == "组会"
    assert result.attempts == 2

    # Verify attempts recorded: gen+verify (attempt 1), gen+verify (attempt 2)
    async with factory() as session:
        rows = (
            await session.execute(
                select(ExtractionAttempt).where(
                    ExtractionAttempt.extraction_group_id == result.extraction_group_id
                )
            )
        ).scalars().all()
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_max_attempts_falls_back_to_pending_review(test_db, stub_llm):
    settings = get_settings()
    # 3 attempts, all rejected
    for _ in range(settings.EXTRACTION_MAX_ATTEMPTS):
        stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": _t()}]))
        stub_llm.push(_verify(False, ["不通过"]))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.status == "pending_review"
    assert len(result.reminders) == 1
    assert result.reminders[0].status == "pending_review"
    assert result.attempts == settings.EXTRACTION_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_schema_error_triggers_retry(test_db, stub_llm):
    """Garbage JSON on first attempt should trigger retry with feedback."""
    settings = get_settings()
    stub_llm.push("not json at all")  # parse fail
    stub_llm.push(_gen([{"kind": "event", "title": "组会", "target_at": _t()}]))
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.status == "success"
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_invalid_draft_in_array_triggers_retry(test_db, stub_llm):
    """deadline with end_at should be rejected by schema → retry."""
    settings = get_settings()
    stub_llm.push(
        _gen(
            [
                {
                    "kind": "deadline",
                    "title": "x",
                    "target_at": _t(),
                    "end_at": _t(48),
                }
            ]
        )
    )
    stub_llm.push(_gen([{"kind": "deadline", "title": "x", "target_at": _t()}]))
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.status == "success"
    assert result.reminders[0].end_at is None


@pytest.mark.asyncio
async def test_advance_reminders_explicit_value_preserved(test_db, stub_llm):
    settings = get_settings()
    stub_llm.push(
        _gen(
            [
                {
                    "kind": "deadline",
                    "title": "x",
                    "target_at": _t(),
                    "advance_reminders_minutes": [10080],
                }
            ]
        )
    )
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.reminders[0].advance_reminders_minutes == [10080]


@pytest.mark.asyncio
async def test_verify_disabled_skips_verify_calls(test_db, stub_llm, monkeypatch):
    monkeypatch.setenv("EXTRACTION_VERIFY_ENABLED", "false")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = get_settings()
    assert settings.EXTRACTION_VERIFY_ENABLED is False

    stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": _t()}]))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.status == "success"
    # Only one LLM call (generate); no verify
    assert len(stub_llm.calls) == 1

    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_llm_network_error_is_recorded_and_retried(test_db, stub_llm):
    settings = get_settings()
    stub_llm.push_error(RuntimeError("network down"))
    stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": _t()}]))
    stub_llm.push(_verify(True))

    extractor = ExtractorService(stub_llm, settings)
    factory = get_session_factory()
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.status == "success"
    assert result.attempts == 2

    async with factory() as session:
        rows = (
            await session.execute(
                select(ExtractionAttempt).where(
                    ExtractionAttempt.extraction_group_id == result.extraction_group_id
                )
            )
        ).scalars().all()
    errors = [r for r in rows if r.error is not None]
    assert any("network down" in (r.error or "") for r in errors)
