from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.db import get_session_factory
from app.models import Reminder, ReminderStatus
from app.services.notifier import (
    EVENT_REMINDER_CREATED,
    EVENT_REMINDER_DUE,
    EVENT_REMINDER_UPDATED,
    NotificationService,
    get_broker,
    mark_past_offsets_as_fired,
)


def _utc(hours_from_now: int = 24, *, minutes_from_now: int = 0) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours_from_now, minutes=minutes_from_now)


async def _create_reminder(
    kind: str = "event",
    target_at: datetime | None = None,
    advance_reminders_minutes: list[int] | None = None,
    status: str = ReminderStatus.PENDING.value,
) -> str:
    factory = get_session_factory()
    async with factory() as session:
        r = Reminder(
            kind=kind,
            title="x",
            target_at=target_at or _utc(24),
            advance_reminders_minutes=advance_reminders_minutes or [0],
            fired_offsets=[],
            status=status,
            source_text="x",
            source_channel="test",
            participants=[],
        )
        session.add(r)
        await session.commit()
        return r.id


# ===== mark_past_offsets_as_fired =====


def test_mark_past_offsets_skips_already_passed():
    """deadline tomorrow with [1440, 60]: 1440 (yesterday) skipped, 60 (in 23h) kept."""
    r = Reminder(
        kind="deadline",
        title="x",
        target_at=_utc(24),  # tomorrow
        advance_reminders_minutes=[1440, 60],
        fired_offsets=[],
        status=ReminderStatus.PENDING.value,
        source_text="x",
        source_channel="test",
        participants=[],
    )
    skipped = mark_past_offsets_as_fired(r)
    assert skipped == [1440]
    assert r.fired_offsets == [1440]


def test_mark_past_offsets_keeps_future_ones():
    r = Reminder(
        kind="event",
        title="x",
        target_at=_utc(48),  # 2 days out
        advance_reminders_minutes=[0, 60, 1440],
        fired_offsets=[],
        status=ReminderStatus.PENDING.value,
        source_text="x",
        source_channel="test",
        participants=[],
    )
    skipped = mark_past_offsets_as_fired(r)
    assert skipped == []
    assert r.fired_offsets == []


def test_mark_past_offsets_skips_all_if_target_past():
    r = Reminder(
        kind="event",
        title="x",
        target_at=_utc(-24),  # already past
        advance_reminders_minutes=[0, 60],
        fired_offsets=[],
        status=ReminderStatus.PENDING.value,
        source_text="x",
        source_channel="test",
        participants=[],
    )
    skipped = mark_past_offsets_as_fired(r)
    assert set(skipped) == {0, 60}


# ===== NotificationService.tick =====


@pytest.mark.asyncio
async def test_tick_fires_due_offsets(test_db):
    broker = get_broker()
    q = await broker.subscribe()

    # Reminder with offset 60 → due at target-1h; we make target 30min from now,
    # so the 60-min offset is already due
    target = _utc(0, minutes_from_now=30)
    rid = await _create_reminder(
        kind="event",
        target_at=target,
        advance_reminders_minutes=[60, 0],
    )

    notifier = NotificationService(broker, get_session_factory())
    fired = await notifier.tick()
    assert fired == 1

    # Verify event payload
    event = await q.get()
    assert event.type == EVENT_REMINDER_DUE
    assert event.data["reminder_id"] == rid
    assert event.data["offset_minutes"] == 60
    assert event.data["kind"] == "event"

    # DB state: fired_offsets updated
    factory = get_session_factory()
    async with factory() as session:
        r = await session.get(Reminder, rid)
    assert r is not None
    assert 60 in r.fired_offsets
    assert 0 not in r.fired_offsets


@pytest.mark.asyncio
async def test_tick_does_not_refire_already_fired(test_db):
    broker = get_broker()
    target = _utc(0, minutes_from_now=30)
    rid = await _create_reminder(
        kind="event",
        target_at=target,
        advance_reminders_minutes=[60],
    )

    notifier = NotificationService(broker, get_session_factory())
    await notifier.tick()
    # Drain
    factory = get_session_factory()
    async with factory() as session:
        r = await session.get(Reminder, rid)
    assert r.fired_offsets == [60]

    # Second tick should fire 0
    fired = await notifier.tick()
    assert fired == 0


@pytest.mark.asyncio
async def test_tick_marks_notified_when_all_fired_and_past_target(test_db):
    broker = get_broker()
    q = await broker.subscribe()

    target = _utc(0, minutes_from_now=-1)  # already past
    rid = await _create_reminder(
        kind="event",
        target_at=target,
        advance_reminders_minutes=[0],
    )

    notifier = NotificationService(broker, get_session_factory())
    await notifier.tick()

    factory = get_session_factory()
    async with factory() as session:
        r = await session.get(Reminder, rid)
    assert r.status == ReminderStatus.NOTIFIED.value

    # Two events: reminder_due then reminder_updated
    events = []
    while not q.empty():
        events.append(await q.get())
    types = [e.type for e in events]
    assert EVENT_REMINDER_DUE in types
    assert EVENT_REMINDER_UPDATED in types


@pytest.mark.asyncio
async def test_tick_skips_non_pending(test_db):
    broker = get_broker()
    target = _utc(0, minutes_from_now=30)
    await _create_reminder(
        kind="event",
        target_at=target,
        advance_reminders_minutes=[60],
        status=ReminderStatus.DONE.value,
    )
    notifier = NotificationService(broker, get_session_factory())
    fired = await notifier.tick()
    assert fired == 0


@pytest.mark.asyncio
async def test_deadline_multi_offsets_fire_sequentially(test_db):
    """Simulate time progression: first only 1440 fires, then 60 fires later."""
    broker = get_broker()
    notifier = NotificationService(broker, get_session_factory())

    target = _utc(72)  # 3 days from now
    rid = await _create_reminder(
        kind="deadline",
        target_at=target,
        advance_reminders_minutes=[60, 1440],
    )

    # Drive tick with "now = target - 23 hours": 1440-offset (24h before) is due, 60 not yet
    fake_now = target - timedelta(hours=23)
    fired = await notifier.tick(now=fake_now)
    assert fired == 1

    factory = get_session_factory()
    async with factory() as session:
        r = await session.get(Reminder, rid)
    assert r.fired_offsets == [1440]
    assert r.status == ReminderStatus.PENDING.value

    # Drive tick with "now = target - 30 minutes" (60 is now due)
    fake_now = target - timedelta(minutes=30)
    fired = await notifier.tick(now=fake_now)
    assert fired == 1

    async with factory() as session:
        r = await session.get(Reminder, rid)
    assert set(r.fired_offsets) == {60, 1440}
    assert r.status == ReminderStatus.PENDING.value  # not yet past target

    # Drive past target → status becomes notified
    fake_now = target + timedelta(minutes=1)
    await notifier.tick(now=fake_now)
    async with factory() as session:
        r = await session.get(Reminder, rid)
    assert r.status == ReminderStatus.NOTIFIED.value


# ===== Ingest publishes reminder_created =====


@pytest.mark.asyncio
async def test_ingest_publishes_reminder_created(client, stub_llm):
    broker = get_broker()
    q = await broker.subscribe()

    stub_llm.push(
        json.dumps(
            {
                "reminders": [
                    {
                        "kind": "event",
                        "title": "组会",
                        "target_at": _utc(48).isoformat(),
                    }
                ]
            }
        )
    )
    stub_llm.push(json.dumps({"pass": True, "issues": []}))

    r = await client.post("/ingest", json={"text": "明天开组会"})
    assert r.status_code == 200

    event = await q.get()
    assert event.type == EVENT_REMINDER_CREATED
    assert event.data["title"] == "组会"
    assert event.data["kind"] == "event"


@pytest.mark.asyncio
async def test_manual_create_publishes_reminder_created(client):
    broker = get_broker()
    q = await broker.subscribe()
    r = await client.post(
        "/reminders",
        json={"kind": "deadline", "title": "x", "target_at": _utc(48).isoformat()},
    )
    assert r.status_code == 201
    event = await q.get()
    assert event.type == EVENT_REMINDER_CREATED


@pytest.mark.asyncio
async def test_done_and_delete_publish_events(client):
    broker = get_broker()
    r = await client.post(
        "/reminders",
        json={"kind": "event", "title": "x", "target_at": _utc(48).isoformat()},
    )
    rid = r.json()["id"]

    q = await broker.subscribe()
    r2 = await client.post(f"/reminders/{rid}/done")
    assert r2.status_code == 200
    event = await q.get()
    assert event.type == EVENT_REMINDER_UPDATED
    assert event.data["status"] == "done"

    r3 = await client.delete(f"/reminders/{rid}")
    assert r3.status_code == 204
    event = await q.get()
    assert event.type == "reminder_deleted"
    assert event.data["reminder_id"] == rid
