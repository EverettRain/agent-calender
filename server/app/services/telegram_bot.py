"""Telegram bot integration.

Single-process embedded in FastAPI:
- Application is constructed at lifespan startup, webhook is set with Telegram.
- Webhook receives updates via /telegram/webhook → forwarded to Application.process_update.
- A broker subscriber listens for reminder_due events and pushes Telegram messages.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape as html_escape
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.models import Reminder, ReminderKind, ReminderStatus
from app.services.extractor import ExtractorService
from app.services.notifier import (
    EVENT_REMINDER_DUE,
    EventBroker,
    mark_past_offsets_as_fired,
)

log = structlog.get_logger(__name__)


# ===== Module-level state =====


@dataclass
class TelegramRuntime:
    application: Application
    settings: Settings
    session_factory: Any
    extractor_provider: Any  # callable: () -> ExtractorService
    broker: EventBroker
    forwarder_task: asyncio.Task | None = None
    # Background tasks for snooze re-pushes; kept so they aren't GC'd mid-await
    pending_tasks: set[asyncio.Task] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.pending_tasks is None:
            self.pending_tasks = set()


_runtime: TelegramRuntime | None = None


def get_runtime() -> TelegramRuntime | None:
    return _runtime


# ===== Lifespan helpers =====


async def start_telegram(
    *,
    settings: Settings,
    session_factory: Any,
    extractor_provider: Any,
    broker: EventBroker,
) -> TelegramRuntime | None:
    """Build + initialize the PTB Application, register webhook, start the broker forwarder.

    Returns None when bot is disabled (no token / no public URL).
    """
    global _runtime
    if not settings.telegram_enabled:
        log.info("telegram.disabled", reason="token or PUBLIC_BASE_URL missing")
        return None

    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .updater(None)  # webhook mode — no internal updater
        .build()
    )

    _register_handlers(application, settings)

    await application.initialize()

    webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/telegram/webhook"
    try:
        await application.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET or None,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        log.info("telegram.webhook_set", url=webhook_url)
    except TelegramError as exc:
        log.error("telegram.set_webhook_failed", error=str(exc))

    await application.start()

    runtime = TelegramRuntime(
        application=application,
        settings=settings,
        session_factory=session_factory,
        extractor_provider=extractor_provider,
        broker=broker,
    )
    runtime.forwarder_task = asyncio.create_task(_broker_forwarder(runtime))
    _runtime = runtime
    return runtime


async def stop_telegram() -> None:
    global _runtime
    if _runtime is None:
        return
    runtime, _runtime = _runtime, None
    if runtime.forwarder_task:
        runtime.forwarder_task.cancel()
        from contextlib import suppress
        with suppress(asyncio.CancelledError, Exception):
            await runtime.forwarder_task
    try:
        await runtime.application.stop()
        await runtime.application.shutdown()
    except Exception as exc:
        log.warning("telegram.shutdown_error", error=str(exc))


# ===== Webhook authorization =====


def chat_authorized(chat_id: int, settings: Settings) -> bool:
    allowed = settings.telegram_allowed_chat_ids()
    if not allowed:
        # No whitelist configured → bot only echoes chat_id on /start (registration helper)
        return False
    return chat_id in allowed


# ===== Handlers =====


def _register_handlers(app: Application, settings: Settings) -> None:
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("today", _cmd_today))
    app.add_handler(CommandHandler("week", _cmd_week))
    app.add_handler(CommandHandler("review", _cmd_review))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text)
    )
    app.add_handler(CallbackQueryHandler(_on_callback))


async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    rt = get_runtime()
    if rt is None:
        return
    if chat_authorized(chat_id, rt.settings):
        await update.message.reply_text(
            "你已经授权 ✓\n\n直接发一句话即可记录：\n"
            "  例：明天14点和张三开会，周五前要交报告\n\n"
            "命令：\n"
            "  /today  今日+未来 3 天\n"
            "  /week   未来 7 天\n"
            "  /review 待复核条目\n"
            "  /help   帮助",
        )
    else:
        await update.message.reply_text(
            f"还未授权。请把下面这个 chat_id 加到服务端 "
            f"<code>TELEGRAM_ALLOWED_CHAT_IDS</code> 后重启：\n\n"
            f"<code>{chat_id}</code>",
            parse_mode=ParseMode.HTML,
        )


async def _cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    rt = get_runtime()
    if rt is None or not chat_authorized(update.effective_chat.id, rt.settings):
        return
    await update.message.reply_text(
        "Agent-Calendar 命令\n\n"
        "<b>记录</b>\n"
        "直接发一句中文，例如 \"周五前要交季度报告\" 就会自动建好待办。\n\n"
        "<b>查询</b>\n"
        "  /today  今日 + 未来 3 天\n"
        "  /week   未来 7 天\n"
        "  /review 待复核条目（抽取存疑的，确认或删除）\n\n"
        "<b>到点提醒</b>\n"
        "会自动推送，可以一键 ✓ 完成、🔔 推迟 10 分、🗑 删除。",
        parse_mode=ParseMode.HTML,
    )


async def _cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_window(update, days=3, label="今日 + 未来 3 天")


async def _cmd_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_window(update, days=7, label="未来 7 天")


async def _cmd_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """List pending_review items, each with approve / delete buttons."""
    rt = get_runtime()
    if rt is None or not chat_authorized(update.effective_chat.id, rt.settings):
        return

    async with rt.session_factory() as session:
        stmt = (
            select(Reminder)
            .where(Reminder.status == ReminderStatus.PENDING_REVIEW.value)
            .order_by(Reminder.created_at.desc())
            .limit(30)
        )
        rs = list((await session.execute(stmt)).scalars().unique().all())

    if not rs:
        await update.message.reply_text("✅ 没有待复核的条目")
        return

    await update.message.reply_text(
        f"<b>待复核 · {len(rs)} 条</b>\n抽取后审核未通过，确认无误就点通过。",
        parse_mode=ParseMode.HTML,
    )
    for r in rs:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✓ 通过", callback_data=f"approve:{r.id}"),
                    InlineKeyboardButton("🗑 删除", callback_data=f"del:{r.id}"),
                ]
            ]
        )
        await rt.application.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_format_reminder_html(r),
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )


async def _on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Free-form text → ingest via LLM."""
    rt = get_runtime()
    if rt is None or not chat_authorized(update.effective_chat.id, rt.settings):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    await update.message.chat.send_action("typing")
    await update.message.reply_text("⏳ 正在智能识别…")

    try:
        async with rt.session_factory() as session:
            extractor: ExtractorService = rt.extractor_provider()
            result = await extractor.extract(session, text=text, source_channel="telegram")
            await session.commit()
    except Exception as exc:
        log.exception("telegram.ingest_failed", error=str(exc))
        await update.message.reply_text(f"❌ 失败：{exc}")
        return

    if not result.reminders:
        await update.message.reply_text("⚠️ 这次没识别出有效条目，请换个说法试试")
        return

    head = "✅ 已识别 " + str(len(result.reminders)) + " 条" + (
        "（待复核，结果可能有误）" if result.status == "pending_review" else ""
    )
    body = "\n\n".join(_format_reminder_html(r) for r in result.reminders)
    await update.message.reply_text(
        f"{head}\n\n{body}",
        parse_mode=ParseMode.HTML,
    )


async def _on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    rt = get_runtime()
    cq = update.callback_query
    if cq is None or rt is None:
        return
    chat_id = cq.message.chat.id if cq.message else None
    if chat_id is None or not chat_authorized(chat_id, rt.settings):
        await cq.answer("未授权")
        return

    data = cq.data or ""
    parts = data.split(":")
    op = parts[0]
    rid = parts[1] if len(parts) > 1 else ""

    try:
        if op == "done":
            await _action_done(rid, rt)
            await cq.answer("已完成 ✓")
            await _edit_after_action(cq, "✓ 已完成")
        elif op == "del":
            await _action_delete(rid, rt)
            await cq.answer("已删除 🗑")
            await _edit_after_action(cq, "🗑 已删除")
        elif op == "snooze":
            minutes = int(parts[2]) if len(parts) > 2 else 10
            await _action_snooze(rid, minutes, rt, chat_id)
            await cq.answer(f"已推迟 {minutes} 分钟 🔔")
            await _edit_after_action(cq, f"🔔 已推迟 {minutes} 分钟")
        elif op == "approve":
            await _action_approve(rid, rt)
            await cq.answer("已通过 ✓")
            await _edit_after_action(cq, "✓ 已通过复核")
        else:
            await cq.answer("未知操作")
    except Exception as exc:
        log.exception("telegram.callback_failed", error=str(exc))
        await cq.answer(f"失败：{exc}", show_alert=True)


async def _edit_after_action(cq, status_line: str) -> None:
    """Rewrite the original message in place to show the completed action,
    and remove the inline keyboard so it can't be clicked twice."""
    original = cq.message.text_html or cq.message.text or ""
    new_text = f"<s>{original}</s>\n\n{status_line}"
    try:
        await cq.edit_message_text(
            text=new_text,
            parse_mode=ParseMode.HTML,
            reply_markup=None,
        )
    except TelegramError as exc:
        log.warning("telegram.edit_after_action_failed", error=str(exc))


# ===== Inline actions =====


async def _action_done(reminder_id: str, rt: TelegramRuntime) -> None:
    async with rt.session_factory() as session:
        r = await session.get(Reminder, reminder_id)
        if r is None:
            raise ValueError("reminder not found")
        r.status = ReminderStatus.DONE.value
        await session.commit()


async def _action_delete(reminder_id: str, rt: TelegramRuntime) -> None:
    async with rt.session_factory() as session:
        r = await session.get(Reminder, reminder_id)
        if r is None:
            raise ValueError("reminder not found")
        r.status = ReminderStatus.CANCELLED.value
        await session.commit()


async def _action_approve(reminder_id: str, rt: TelegramRuntime) -> None:
    """pending_review → pending (accept the extraction as-is)."""
    async with rt.session_factory() as session:
        r = await session.get(Reminder, reminder_id)
        if r is None:
            raise ValueError("reminder not found")
        if r.status == ReminderStatus.PENDING_REVIEW.value:
            r.status = ReminderStatus.PENDING.value
            await session.commit()


async def _action_snooze(
    reminder_id: str, minutes: int, rt: TelegramRuntime, chat_id: int
) -> None:
    """Schedule a one-shot re-push without changing the underlying target_at."""

    async def fire_later() -> None:
        await asyncio.sleep(minutes * 60)
        try:
            async with rt.session_factory() as session:
                r = await session.get(Reminder, reminder_id)
                if r is None or r.status in (
                    ReminderStatus.DONE.value,
                    ReminderStatus.CANCELLED.value,
                ):
                    return
                msg = _format_reminder_due(r, offset_minutes=0, snoozed=True)
                kb = _action_keyboard(r.id)
                await rt.application.bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
        except Exception as exc:
            log.warning("telegram.snooze_fire_failed", error=str(exc))

    task = asyncio.create_task(fire_later())
    rt.pending_tasks.add(task)
    task.add_done_callback(rt.pending_tasks.discard)


# ===== Listing helpers =====


async def _send_window(update: Update, *, days: int, label: str) -> None:
    rt = get_runtime()
    if rt is None or not chat_authorized(update.effective_chat.id, rt.settings):
        return

    now = datetime.now(UTC)
    end = now + timedelta(days=days)

    async with rt.session_factory() as session:
        stmt = (
            select(Reminder)
            .where(
                Reminder.target_at >= now - timedelta(hours=1),
                Reminder.target_at <= end,
                Reminder.status.notin_(
                    [ReminderStatus.DONE.value, ReminderStatus.CANCELLED.value]
                ),
            )
            .order_by(Reminder.target_at.asc())
            .limit(50)
        )
        result = await session.execute(stmt)
        reminders: Iterable[Reminder] = result.scalars().unique().all()
        rs = list(reminders)

    if not rs:
        await update.message.reply_text(f"📭 {label} 没有待办")
        return

    body = "\n\n".join(_format_reminder_html(r) for r in rs)
    await update.message.reply_text(
        f"<b>{label} · {len(rs)} 条</b>\n\n{body}",
        parse_mode=ParseMode.HTML,
    )


# ===== Push reminder_due =====


async def _broker_forwarder(rt: TelegramRuntime) -> None:
    queue = await rt.broker.subscribe()
    try:
        while True:
            event = await queue.get()
            if event.type != EVENT_REMINDER_DUE:
                continue
            await _push_reminder_due(rt, event.data)
    except asyncio.CancelledError:
        await rt.broker.unsubscribe(queue)
        raise


async def _push_reminder_due(rt: TelegramRuntime, data: dict[str, Any]) -> None:
    rid = data.get("reminder_id")
    if not rid:
        return
    async with rt.session_factory() as session:
        r = await session.get(Reminder, rid)
        if r is None:
            return
        text = _format_reminder_due(
            r, offset_minutes=int(data.get("offset_minutes", 0))
        )
        kb = _action_keyboard(r.id)

    for chat_id in rt.settings.telegram_allowed_chat_ids():
        try:
            await rt.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        except TelegramError as exc:
            log.warning("telegram.push_failed", chat_id=chat_id, error=str(exc))


# ===== Formatting =====


def _action_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✓ 完成", callback_data=f"done:{reminder_id}"),
                InlineKeyboardButton("🔔 推迟 10 分", callback_data=f"snooze:{reminder_id}:10"),
                InlineKeyboardButton("🗑 删除", callback_data=f"del:{reminder_id}"),
            ],
        ]
    )


def _local_dt(dt: datetime, tz: str) -> str:
    return dt.astimezone(ZoneInfo(tz)).strftime("%m-%d %H:%M")


def _format_reminder_html(r: Reminder) -> str:
    rt = get_runtime()
    tz = rt.settings.TZ if rt else "Asia/Shanghai"
    kind_emoji = "📌" if r.kind == ReminderKind.DEADLINE.value else "📅"
    pieces = [f"{kind_emoji} <b>{html_escape(r.title)}</b>"]
    pieces.append(f"  ⏰ {_local_dt(r.target_at, tz)}")
    if r.location:
        pieces.append(f"  📍 {html_escape(r.location)}")
    if r.participants:
        pieces.append(f"  👥 {html_escape(', '.join(r.participants))}")
    tag_strs: list[str] = []
    if r.tags:
        tag_strs.extend(f"#{html_escape(t.name)}" for t in r.tags)
    if tag_strs:
        pieces.append("  " + " ".join(tag_strs))
    return "\n".join(pieces)


def _format_reminder_due(
    r: Reminder, *, offset_minutes: int, snoozed: bool = False
) -> str:
    rt = get_runtime()
    tz = rt.settings.TZ if rt else "Asia/Shanghai"
    when = _local_dt(r.target_at, tz)
    title = html_escape(r.title)

    if snoozed:
        head = f"🔔 推迟提醒：<b>{title}</b>"
    elif r.kind == ReminderKind.DEADLINE.value:
        if offset_minutes >= 1440:
            head = f"📌 距截止还有 {offset_minutes // 1440} 天：<b>{title}</b>"
        elif offset_minutes >= 60:
            head = f"📌 距截止还有 {offset_minutes // 60} 小时：<b>{title}</b>"
        elif offset_minutes > 0:
            head = f"📌 距截止还有 {offset_minutes} 分钟：<b>{title}</b>"
        else:
            head = f"📌 已到截止时间：<b>{title}</b>"
    else:  # event
        if offset_minutes > 0:
            head = f"📅 还有 {offset_minutes} 分钟开始：<b>{title}</b>"
        else:
            head = f"📅 事件开始：<b>{title}</b>"

    body = [head, f"  ⏰ {when}"]
    if r.description:
        body.append(f"  📝 {html_escape(r.description)}")
    if r.location:
        body.append(f"  📍 {html_escape(r.location)}")
    if r.participants:
        body.append(f"  👥 {html_escape(', '.join(r.participants))}")
    if r.tags:
        body.append("  " + " ".join(f"#{html_escape(t.name)}" for t in r.tags))
    return "\n".join(body)


# Re-exports for tests
mark_past_offsets_as_fired  # noqa: B018
