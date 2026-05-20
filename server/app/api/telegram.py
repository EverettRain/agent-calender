from __future__ import annotations

import hmac
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from telegram import Update

from app.config import Settings, get_settings
from app.services.telegram_bot import get_runtime

router = APIRouter(prefix="/telegram", tags=["telegram"])

# Bounded LRU of recently-seen update_ids for idempotent webhook handling.
_SEEN_UPDATES: OrderedDict[int, None] = OrderedDict()
_SEEN_MAX = 512


def seen_update(update_id: int) -> bool:
    """Return True if this update_id was already processed recently."""
    if update_id in _SEEN_UPDATES:
        return True
    _SEEN_UPDATES[update_id] = None
    if len(_SEEN_UPDATES) > _SEEN_MAX:
        _SEEN_UPDATES.popitem(last=False)
    return False


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    """Endpoint Telegram POSTs new updates to. Authenticated via the secret
    token header (configured during set_webhook)."""

    if not settings.telegram_enabled:
        # Bot disabled — refuse to process; protects against accidental webhooks.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telegram bot disabled")

    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if expected:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(got, expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid webhook secret")

    runtime = get_runtime()
    if runtime is None:
        # Bot enabled in config but not yet bootstrapped — let TG retry later
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "bot not ready")

    payload = await request.json()
    update = Update.de_json(payload, runtime.application.bot)

    # Idempotency: Telegram re-delivers updates it didn't get a timely 200 for.
    # Dedup by update_id so a slow LLM call can't cause double-ingest.
    if update is not None and seen_update(update.update_id):
        return {"ok": True, "duplicate": True}

    # Hand off to the Application's queue and return 200 immediately, so the
    # webhook never blocks on the (15-20s) extraction pipeline.
    await runtime.application.update_queue.put(update)
    return {"ok": True}
