"""In-memory event broker + periodic notification service.

Single-user, single-worker design — no Redis/queue needed. The broker keeps
asyncio.Queues per SSE subscriber; the notifier scans the DB every tick and
fires unprocessed offsets.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select

from app.models import Reminder, ReminderStatus

log = structlog.get_logger(__name__)

# ===== Event payload types =====

EVENT_REMINDER_CREATED = "reminder_created"
EVENT_REMINDER_UPDATED = "reminder_updated"
EVENT_REMINDER_DELETED = "reminder_deleted"
EVENT_REMINDER_DUE = "reminder_due"
EVENT_PING = "ping"


@dataclass(slots=True)
class Event:
    type: str
    data: dict[str, Any]


# ===== EventBroker =====


class EventBroker:
    """In-process pub/sub for SSE subscribers."""

    def __init__(self, *, max_queue_size: int = 100) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size

    async def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            self._subscribers.add(q)
        log.debug("broker.subscribed", count=len(self._subscribers))
        return q

    async def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        async with self._lock:
            self._subscribers.discard(q)
        log.debug("broker.unsubscribed", count=len(self._subscribers))

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        event = Event(type=event_type, data=data)
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow subscriber: drop the event for that subscriber, don't block others
                log.warning("broker.queue_full_drop", event_type=event_type)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


_broker: EventBroker | None = None


def get_broker() -> EventBroker:
    global _broker
    if _broker is None:
        _broker = EventBroker()
    return _broker


def reset_broker_for_tests() -> None:
    """Allow tests to start each scenario with a clean broker."""
    global _broker
    _broker = EventBroker()


# ===== Past-due offsets handling =====


def mark_past_offsets_as_fired(
    reminder: Reminder, now: datetime | None = None
) -> list[int]:
    """For a freshly-created reminder, mark offsets whose fire-time is already
    in the past as "fired" without publishing — we don't backfill missed pings.

    Returns the offsets that were skipped (for logging/inspection).
    """
    now = now or datetime.now(UTC)
    if reminder.target_at.tzinfo is None:
        raise ValueError("target_at must be tz-aware")

    fired = list(reminder.fired_offsets or [])
    skipped: list[int] = []
    for offset in reminder.advance_reminders_minutes or []:
        if offset in fired:
            continue
        fire_at = reminder.target_at - timedelta(minutes=offset)
        if fire_at < now:
            fired.append(offset)
            skipped.append(offset)
    reminder.fired_offsets = sorted(set(fired))
    return skipped


# ===== NotificationService =====


def _serialize_reminder(reminder: Reminder) -> dict[str, Any]:
    return {
        "id": reminder.id,
        "kind": reminder.kind,
        "title": reminder.title,
        "target_at": reminder.target_at.isoformat(),
        "advance_reminders_minutes": list(reminder.advance_reminders_minutes or []),
        "fired_offsets": list(reminder.fired_offsets or []),
        "status": reminder.status,
    }


class NotificationService:
    """Scans pending reminders periodically and fires due notifications."""

    def __init__(self, broker: EventBroker, session_factory) -> None:
        self._broker = broker
        self._session_factory = session_factory

    async def tick(self, now: datetime | None = None) -> int:
        """One scan pass. Returns the number of notifications fired."""
        now = now or datetime.now(UTC)
        fired_count = 0

        async with self._session_factory() as session:
            result = await session.execute(
                select(Reminder).where(
                    Reminder.status == ReminderStatus.PENDING.value
                )
            )
            reminders: Iterable[Reminder] = result.scalars().all()

            for r in reminders:
                fired_set = set(r.fired_offsets or [])
                target_at = r.target_at  # already tz-aware from UTCDateTime
                changed = False

                for offset in sorted(r.advance_reminders_minutes or []):
                    if offset in fired_set:
                        continue
                    fire_at = target_at - timedelta(minutes=offset)
                    if fire_at <= now:
                        await self._broker.publish(
                            EVENT_REMINDER_DUE,
                            {
                                "reminder_id": r.id,
                                "kind": r.kind,
                                "title": r.title,
                                "target_at": target_at.isoformat(),
                                "offset_minutes": offset,
                                "minutes_to_target": int(
                                    (target_at - now).total_seconds() // 60
                                ),
                            },
                        )
                        fired_set.add(offset)
                        changed = True
                        fired_count += 1

                if changed:
                    r.fired_offsets = sorted(fired_set)

                all_offsets_fired = fired_set >= set(r.advance_reminders_minutes or [])
                if (
                    all_offsets_fired
                    and now > target_at
                    and r.status != ReminderStatus.NOTIFIED.value
                ):
                    r.status = ReminderStatus.NOTIFIED.value
                    await self._broker.publish(
                        EVENT_REMINDER_UPDATED,
                        _serialize_reminder(r),
                    )

            await session.commit()

        if fired_count:
            log.info("notifier.tick", fired=fired_count)
        return fired_count
