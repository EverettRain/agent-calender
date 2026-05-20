"""Runtime app-settings + model override tests."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.db import get_session_factory
from app.services.extractor import ExtractorService


def _t(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


@pytest.mark.asyncio
async def test_get_settings_returns_env_defaults(client):
    r = await client.get("/settings")
    assert r.status_code == 200
    body = r.json()
    # env defaults (conftest doesn't override these → from Settings defaults)
    assert body["generate_model"] == "deepseek-v4-pro"
    assert body["verify_model"] == "deepseek-v4-flash"
    assert body["verify_enabled"] is True
    assert body["max_attempts"] == 3
    assert body["token_budget"] == 16000


@pytest.mark.asyncio
async def test_put_settings_overrides(client):
    r = await client.put(
        "/settings",
        json={
            "generate_model": "deepseek-custom-x",
            "verify_enabled": False,
            "max_attempts": 5,
            "token_budget": 20000,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["generate_model"] == "deepseek-custom-x"
    assert body["verify_enabled"] is False
    assert body["max_attempts"] == 5
    assert body["token_budget"] == 20000
    # verify_model untouched → still env default
    assert body["verify_model"] == "deepseek-v4-flash"

    # Persisted: GET returns the same
    r2 = await client.get("/settings")
    assert r2.json()["generate_model"] == "deepseek-custom-x"


@pytest.mark.asyncio
async def test_put_settings_validation(client):
    r = await client.put("/settings", json={"max_attempts": 99})
    assert r.status_code == 422  # > 10
    r = await client.put("/settings", json={"token_budget": 10})
    assert r.status_code == 422  # < 500


@pytest.mark.asyncio
async def test_extractor_uses_db_model_override(test_db, stub_llm):
    """After PUT settings, the extractor should call the LLM with the new model."""
    settings = get_settings()

    # Seed a DB override via the API isn't available here (no client), so write directly
    from app.models import AppSettings

    factory = get_session_factory()
    async with factory() as session:
        session.add(AppSettings(id=1, generate_model="db-generate-model", verify_enabled=False))
        await session.commit()

    stub_llm.push(json.dumps({"reminders": [{"kind": "event", "title": "x", "target_at": _t()}]}))

    extractor = ExtractorService(stub_llm, settings)
    async with factory() as session:
        result = await extractor.extract(session, "原文", "test")
        await session.commit()

    assert result.status == "success"
    # verify disabled via DB → only 1 LLM call, with the DB-configured model
    assert len(stub_llm.calls) == 1
    assert stub_llm.calls[0]["model"] == "db-generate-model"


@pytest.mark.asyncio
async def test_reminder_update_change_kind_to_deadline_clears_range(client, stub_llm):
    """Changing an event (with end_at) to deadline must drop end_at/duration."""
    # Create an event with a duration
    r = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "meeting",
            "target_at": _t(),
            "duration_minutes": 60,
        },
    )
    rid = r.json()["id"]
    assert r.json()["duration_minutes"] == 60

    # Flip to deadline
    r2 = await client.put(f"/reminders/{rid}", json={"kind": "deadline"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["kind"] == "deadline"
    assert body["end_at"] is None
    assert body["duration_minutes"] is None


@pytest.mark.asyncio
async def test_reminder_update_kind_deadline_rejects_explicit_end(client):
    r = await client.post(
        "/reminders",
        json={"kind": "event", "title": "x", "target_at": _t()},
    )
    rid = r.json()["id"]
    # Setting kind=deadline AND providing end_at in the same call → 422
    r2 = await client.put(
        f"/reminders/{rid}",
        json={"kind": "deadline", "end_at": _t(48)},
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_reminder_approve_via_status(client, stub_llm):
    """pending_review → pending by PUT status (App review path)."""
    # Force a pending_review by making verify always fail then exhausting attempts
    for _ in range(3):
        stub_llm.push(json.dumps({"reminders": [{"kind": "event", "title": "x", "target_at": _t()}]}))
        stub_llm.push(json.dumps({"pass": False, "issues": ["nope"]}))

    r = await client.post("/ingest", json={"text": "原文"})
    body = r.json()
    assert body["status"] == "pending_review"
    rid = body["reminders"][0]["id"]

    # Approve via PUT status
    r2 = await client.put(f"/reminders/{rid}", json={"status": "pending"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "pending"
