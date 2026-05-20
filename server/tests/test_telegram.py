"""Telegram bot tests with stubbed PTB Application/Bot."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings, get_settings
from app.db import get_session_factory
from app.models import Reminder, ReminderStatus
from app.services import telegram_bot
from app.services.extractor import ExtractorService
from app.services.notifier import (
    get_broker,
    mark_past_offsets_as_fired,
)


def _utc_future(hours: int = 24) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


# ===== Webhook / disabled state =====


@pytest.mark.asyncio
async def test_webhook_disabled_returns_503(client):
    """When TELEGRAM_BOT_TOKEN is empty, /telegram/webhook should 503 (not 401)."""
    r = await client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "anything"},
    )
    assert r.status_code == 503


# ===== chat_authorized =====


def test_chat_authorized_empty_whitelist_denies_all():
    s = Settings(
        API_TOKEN="token-1234",
        DEEPSEEK_API_KEY="key-xxxx",
        TELEGRAM_ALLOWED_CHAT_IDS="",
    )
    assert telegram_bot.chat_authorized(123, s) is False


def test_chat_authorized_csv_match():
    s = Settings(
        API_TOKEN="token-1234",
        DEEPSEEK_API_KEY="key-xxxx",
        TELEGRAM_ALLOWED_CHAT_IDS="123, 456, 789",
    )
    assert telegram_bot.chat_authorized(123, s)
    assert telegram_bot.chat_authorized(789, s)
    assert telegram_bot.chat_authorized(999, s) is False


def test_chat_authorized_ignores_garbage():
    s = Settings(
        API_TOKEN="token-1234",
        DEEPSEEK_API_KEY="key-xxxx",
        TELEGRAM_ALLOWED_CHAT_IDS="42,not-a-number,100",
    )
    assert telegram_bot.chat_authorized(42, s)
    assert telegram_bot.chat_authorized(100, s)


# ===== Telegram action helpers =====


@pytest.fixture
def stub_runtime(test_db, monkeypatch):
    """Plug a stub runtime with whitelist={1001} into the module global."""
    settings = get_settings()
    monkeypatch.setattr(
        settings, "TELEGRAM_ALLOWED_CHAT_IDS", "1001"
    )

    bot = MagicMock()
    bot.send_message = AsyncMock()
    application = MagicMock()
    application.bot = bot

    runtime = telegram_bot.TelegramRuntime(
        application=application,
        settings=settings,
        session_factory=get_session_factory(),
        extractor_provider=lambda: ExtractorService(MagicMock(), settings),
        broker=get_broker(),
    )
    telegram_bot._runtime = runtime
    yield runtime
    # Cancel any snooze fire_later() tasks so they don't leak past the test
    for task in list(runtime.pending_tasks):
        task.cancel()
    telegram_bot._runtime = None


async def _seed_reminder(kind: str = "event") -> str:
    factory = get_session_factory()
    async with factory() as session:
        r = Reminder(
            kind=kind,
            title="test reminder",
            target_at=_utc_future(2),
            advance_reminders_minutes=[0],
            fired_offsets=[],
            status=ReminderStatus.PENDING.value,
            source_text="x",
            source_channel="test",
            participants=[],
        )
        r.tags = []
        mark_past_offsets_as_fired(r)
        session.add(r)
        await session.commit()
        return r.id


@pytest.mark.asyncio
async def test_action_done_marks_reminder_done(stub_runtime):
    rid = await _seed_reminder()
    await telegram_bot._action_done(rid, stub_runtime)

    async with get_session_factory()() as session:
        r = await session.get(Reminder, rid)
        assert r.status == ReminderStatus.DONE.value


@pytest.mark.asyncio
async def test_action_delete_marks_cancelled(stub_runtime):
    rid = await _seed_reminder()
    await telegram_bot._action_delete(rid, stub_runtime)

    async with get_session_factory()() as session:
        r = await session.get(Reminder, rid)
        assert r.status == ReminderStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_broker_event_triggers_tg_push(stub_runtime):
    """A reminder_due broker event should call bot.send_message for each allowed chat."""
    rid = await _seed_reminder()
    await telegram_bot._push_reminder_due(
        stub_runtime,
        {"reminder_id": rid, "offset_minutes": 0},
    )
    assert stub_runtime.application.bot.send_message.await_count == 1
    call = stub_runtime.application.bot.send_message.await_args
    assert call.kwargs["chat_id"] == 1001
    assert "test reminder" in call.kwargs["text"]
    # Inline keyboard has 3 buttons
    kb = call.kwargs["reply_markup"]
    assert kb is not None
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 3
    assert {b.callback_data.split(":")[0] for b in buttons} == {"done", "snooze", "del"}


@pytest.mark.asyncio
async def test_format_reminder_due_event_vs_deadline(stub_runtime):
    rid_event = await _seed_reminder(kind="event")
    rid_deadline = await _seed_reminder(kind="deadline")

    async with get_session_factory()() as session:
        ev = await session.get(Reminder, rid_event)
        dl = await session.get(Reminder, rid_deadline)

        # At-target message
        msg_e = telegram_bot._format_reminder_due(ev, offset_minutes=0)
        assert "事件开始" in msg_e or "📅" in msg_e

        msg_d = telegram_bot._format_reminder_due(dl, offset_minutes=0)
        assert "截止" in msg_d or "📌" in msg_d

        # Advance reminder
        msg_d_adv = telegram_bot._format_reminder_due(dl, offset_minutes=1440)
        assert "1 天" in msg_d_adv or "天" in msg_d_adv


@pytest.mark.asyncio
async def test_push_skips_when_reminder_deleted(stub_runtime):
    """If the reminder was already deleted, push should silently no-op."""
    await telegram_bot._push_reminder_due(
        stub_runtime,
        {"reminder_id": "00000000-0000-0000-0000-000000000000", "offset_minutes": 0},
    )
    assert stub_runtime.application.bot.send_message.await_count == 0


def _make_callback_query(data: str):
    """Build a stub CallbackQuery for callback-handler tests."""
    cq = MagicMock()
    cq.data = data
    cq.answer = AsyncMock()
    cq.edit_message_text = AsyncMock()
    cq.message = MagicMock()
    cq.message.chat.id = 1001
    cq.message.text_html = "📅 <b>test reminder</b>"
    cq.message.text = "test reminder"
    return cq


def _make_update(cq) -> MagicMock:
    update = MagicMock()
    update.callback_query = cq
    return update


@pytest.mark.parametrize("op,prefix", [("done", "✓"), ("del", "🗑"), ("snooze", "🔔")])
@pytest.mark.asyncio
async def test_callback_removes_keyboard_and_adds_status(stub_runtime, op, prefix):
    """All three inline buttons must strip the keyboard (reply_markup=None) and
    append a status line so they can't be double-clicked."""
    rid = await _seed_reminder()
    data = f"{op}:{rid}:10" if op == "snooze" else f"{op}:{rid}"
    cq = _make_callback_query(data)

    await telegram_bot._on_callback(_make_update(cq), MagicMock())

    # answered (removes the loading spinner)
    assert cq.answer.await_count == 1
    # message edited with keyboard removed
    assert cq.edit_message_text.await_count == 1
    kwargs = cq.edit_message_text.await_args.kwargs
    assert kwargs["reply_markup"] is None
    assert prefix in kwargs["text"]
    # original text struck through
    assert "<s>" in kwargs["text"]


@pytest.mark.asyncio
async def test_callback_unauthorized_chat_denied(stub_runtime):
    rid = await _seed_reminder()
    cq = _make_callback_query(f"done:{rid}")
    cq.message.chat.id = 999999  # not in whitelist
    await telegram_bot._on_callback(_make_update(cq), MagicMock())
    cq.answer.assert_awaited_once_with("未授权")
    cq.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_callback_moves_pending_review_to_pending(stub_runtime):
    # Seed a pending_review reminder directly
    factory = get_session_factory()
    async with factory() as session:
        r = Reminder(
            kind="event",
            title="needs review",
            target_at=_utc_future(2),
            advance_reminders_minutes=[0],
            fired_offsets=[],
            status=ReminderStatus.PENDING_REVIEW.value,
            source_text="x",
            source_channel="test",
            participants=[],
        )
        r.tags = []
        session.add(r)
        await session.commit()
        rid = r.id

    cq = _make_callback_query(f"approve:{rid}")
    await telegram_bot._on_callback(_make_update(cq), MagicMock())

    async with factory() as session:
        fresh = await session.get(Reminder, rid)
        assert fresh.status == ReminderStatus.PENDING.value
    assert cq.edit_message_text.await_count == 1


# ===== Webhook idempotency =====


def test_seen_update_dedup():
    from app.api import telegram as tg_api

    tg_api._SEEN_UPDATES.clear()
    assert tg_api.seen_update(1001) is False  # first time
    assert tg_api.seen_update(1001) is True   # duplicate
    assert tg_api.seen_update(1002) is False


def test_seen_update_lru_bound():
    from app.api import telegram as tg_api

    tg_api._SEEN_UPDATES.clear()
    for i in range(tg_api._SEEN_MAX + 50):
        tg_api.seen_update(i)
    # Oldest evicted; size capped
    assert len(tg_api._SEEN_UPDATES) <= tg_api._SEEN_MAX
    # A very old id should have been evicted → treated as new again
    assert tg_api.seen_update(0) is False


# ===== End-to-end broker integration =====


@pytest.mark.asyncio
async def test_notifier_tick_propagates_to_tg(test_db, stub_runtime):
    """Full path: NotificationService.tick → broker event → forwarder picks up → TG push."""
    from app.services.notifier import NotificationService

    # Create reminder that's due now (offset 0, target 1 min ago)
    factory = get_session_factory()
    async with factory() as session:
        r = Reminder(
            kind="event",
            title="due now",
            target_at=datetime.now(UTC) - timedelta(minutes=1),
            advance_reminders_minutes=[0],
            fired_offsets=[],
            status=ReminderStatus.PENDING.value,
            source_text="x",
            source_channel="test",
            participants=[],
        )
        r.tags = []
        session.add(r)
        await session.commit()

    # Drive tick + manually invoke the push (we don't run the forwarder task here)
    notifier = NotificationService(get_broker(), factory)
    fired = await notifier.tick()
    assert fired == 1

    # Consume the event the broker would have queued + push via our helper
    # (in production the forwarder task does this)
    # We can replay the published events by drain-checking subscribers,
    # but simplest: call _push_reminder_due directly with the event payload
    async with factory() as session:
        r_loaded = (await session.execute(
            __import__("sqlalchemy").select(Reminder)
        )).scalars().first()

    await telegram_bot._push_reminder_due(
        stub_runtime,
        {"reminder_id": r_loaded.id, "offset_minutes": 0},
    )
    assert stub_runtime.application.bot.send_message.await_count == 1
