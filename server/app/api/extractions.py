from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, require_token
from app.models import ExtractionAttempt, Reminder
from app.schemas import (
    ExtractionAttemptOut,
    ExtractionGroupOut,
    ReminderOut,
)

router = APIRouter(prefix="/extractions", tags=["extractions"], dependencies=[Depends(require_token)])


@router.get("/{group_id}", response_model=ExtractionGroupOut)
async def get_extraction_group(
    group_id: str,
    session: AsyncSession = Depends(db_session),
) -> ExtractionGroupOut:
    attempts_result = await session.execute(
        select(ExtractionAttempt)
        .where(ExtractionAttempt.extraction_group_id == group_id)
        .order_by(ExtractionAttempt.attempt_no.asc(), ExtractionAttempt.created_at.asc())
    )
    attempts = list(attempts_result.scalars().all())
    if not attempts:
        raise HTTPException(404, "extraction group not found")

    reminders_result = await session.execute(
        select(Reminder)
        .where(Reminder.extraction_group_id == group_id)
        .order_by(Reminder.target_at.asc())
    )
    reminders = list(reminders_result.scalars().all())

    return ExtractionGroupOut(
        extraction_group_id=group_id,
        source_text=attempts[0].source_text,
        attempts=[ExtractionAttemptOut.model_validate(a) for a in attempts],
        reminders=[ReminderOut.model_validate(r) for r in reminders],
    )
