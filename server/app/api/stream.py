from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.deps import require_token
from app.services.notifier import EVENT_PING, get_broker

router = APIRouter(prefix="/stream", tags=["stream"], dependencies=[Depends(require_token)])

_HEARTBEAT_INTERVAL_SECONDS = 15.0


@router.get("")
async def stream(request: Request) -> EventSourceResponse:
    """Server-Sent Events stream. Sends reminder_created / reminder_updated /
    reminder_due / ping (heartbeat) events.

    Client should reconnect on disconnect (EventSource does this automatically).
    """
    broker = get_broker()
    queue = await broker.subscribe()

    async def event_generator() -> AsyncIterator[dict]:
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_HEARTBEAT_INTERVAL_SECONDS
                    )
                    yield {
                        "event": event.type,
                        "data": json.dumps(event.data, ensure_ascii=False),
                    }
                except TimeoutError:
                    # Heartbeat keeps the connection alive through proxies/firewalls
                    yield {"event": EVENT_PING, "data": ""}
        finally:
            await broker.unsubscribe(queue)

    return EventSourceResponse(event_generator())
