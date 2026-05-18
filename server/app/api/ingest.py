from __future__ import annotations

import gc

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, get_extractor, require_token
from app.schemas import IngestRequest, IngestResponse, ReminderOut
from app.services.extractor import ExtractorService
from app.services.notifier import EVENT_REMINDER_CREATED, get_broker

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_token)])


@router.post("", response_model=IngestResponse)
async def ingest(
    payload: IngestRequest,
    session: AsyncSession = Depends(db_session),
    extractor: ExtractorService = Depends(get_extractor),
) -> IngestResponse:
    try:
        result = await extractor.extract(
            session,
            text=payload.text,
            source_channel=payload.source_channel,
        )
        await session.commit()

        reminders_out = [ReminderOut.model_validate(r) for r in result.reminders]

        broker = get_broker()
        for r in reminders_out:
            await broker.publish(EVENT_REMINDER_CREATED, r.model_dump(mode="json"))

        return IngestResponse(
            extraction_group_id=result.extraction_group_id,
            status=result.status,
            reminders=reminders_out,
            attempts=result.attempts,
            total_tokens=result.total_tokens,
        )
    finally:
        # LLM responses are large; encourage prompt cleanup under tight RAM budget
        gc.collect()
