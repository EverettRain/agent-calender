from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest


def _t(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _gen(items) -> str:
    return json.dumps({"reminders": items})


def _verify(passed: bool, issues=None) -> str:
    return json.dumps({"pass": passed, "issues": issues or []})


@pytest.mark.asyncio
async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ingest_requires_token(client):
    r = await client.post(
        "/ingest",
        json={"text": "明天开组会"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ingest_creates_mixed_reminders(client, stub_llm):
    stub_llm.push(
        _gen(
            [
                {"kind": "event", "title": "和张三开会", "target_at": _t()},
                {"kind": "deadline", "title": "交报告", "target_at": _t(72)},
            ]
        )
    )
    stub_llm.push(_verify(True))

    r = await client.post(
        "/ingest",
        json={"text": "明天 14 点和张三开会，另外周五前要交报告"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert len(body["reminders"]) == 2

    by_kind = {x["kind"]: x for x in body["reminders"]}
    assert by_kind["event"]["advance_reminders_minutes"] == [0]
    assert by_kind["deadline"]["advance_reminders_minutes"] == [60, 1440]

    # Group ID consistent
    group_id = body["extraction_group_id"]
    assert all(r["extraction_group_id"] == group_id for r in body["reminders"])


@pytest.mark.asyncio
async def test_extraction_group_endpoint(client, stub_llm):
    stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": _t()}]))
    stub_llm.push(_verify(False, ["不通过"]))
    stub_llm.push(_gen([{"kind": "event", "title": "组会", "target_at": _t()}]))
    stub_llm.push(_verify(True))

    r = await client.post("/ingest", json={"text": "原文"})
    body = r.json()
    group_id = body["extraction_group_id"]

    r2 = await client.get(f"/extractions/{group_id}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["extraction_group_id"] == group_id
    assert len(detail["attempts"]) == 4  # 2 gen + 2 verify
    assert len(detail["reminders"]) == 1


@pytest.mark.asyncio
async def test_extraction_group_404(client):
    r = await client.get("/extractions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_reminders_filters(client, stub_llm):
    stub_llm.push(
        _gen(
            [
                {"kind": "event", "title": "e", "target_at": _t()},
                {"kind": "deadline", "title": "d", "target_at": _t(48)},
            ]
        )
    )
    stub_llm.push(_verify(True))
    await client.post("/ingest", json={"text": "原文"})

    r = await client.get("/reminders?kind=deadline")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["kind"] == "deadline"


@pytest.mark.asyncio
async def test_manual_create_reminder(client):
    r = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "手动条目",
            "target_at": _t(),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "event"
    assert body["source_channel"] == "manual"
    # Default offsets applied
    assert body["advance_reminders_minutes"] == [0]


@pytest.mark.asyncio
async def test_manual_create_deadline_with_explicit_offsets(client):
    r = await client.post(
        "/reminders",
        json={
            "kind": "deadline",
            "title": "提交申请",
            "target_at": _t(72),
            "advance_reminders_minutes": [10080, 1440, 60, 60],  # dup gets normalized
        },
    )
    assert r.status_code == 201
    assert r.json()["advance_reminders_minutes"] == [60, 1440, 10080]


@pytest.mark.asyncio
async def test_manual_create_deadline_rejects_end_at(client):
    r = await client.post(
        "/reminders",
        json={
            "kind": "deadline",
            "title": "x",
            "target_at": _t(),
            "end_at": _t(48),
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_reminder_resets_stale_fired_offsets(client, stub_llm):
    stub_llm.push(_gen([{"kind": "deadline", "title": "x", "target_at": _t(72)}]))
    stub_llm.push(_verify(True))
    r = await client.post("/ingest", json={"text": "原文"})
    rid = r.json()["reminders"][0]["id"]

    # Simulate notifier having fired offset 1440 already
    from app.db import get_session_factory
    from app.models import Reminder

    factory = get_session_factory()
    async with factory() as session:
        rem = await session.get(Reminder, rid)
        rem.fired_offsets = [1440, 60]
        await session.commit()

    # Now PUT a new offsets list that drops 1440
    r2 = await client.put(
        f"/reminders/{rid}",
        json={"advance_reminders_minutes": [60, 30]},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["advance_reminders_minutes"] == [30, 60]
    assert body["fired_offsets"] == [60]  # 1440 dropped from fired


@pytest.mark.asyncio
async def test_mark_done_and_delete(client, stub_llm):
    stub_llm.push(_gen([{"kind": "event", "title": "x", "target_at": _t()}]))
    stub_llm.push(_verify(True))
    r = await client.post("/ingest", json={"text": "原文"})
    rid = r.json()["reminders"][0]["id"]

    r2 = await client.post(f"/reminders/{rid}/done")
    assert r2.status_code == 200
    assert r2.json()["status"] == "done"

    r3 = await client.delete(f"/reminders/{rid}")
    assert r3.status_code == 204

    r4 = await client.get(f"/reminders/{rid}")
    assert r4.json()["status"] == "cancelled"
