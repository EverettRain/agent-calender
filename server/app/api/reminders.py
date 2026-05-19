from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, require_token
from app.models import Group, Reminder, ReminderStatus, Tag
from app.schemas import (
    ManualReminderCreate,
    ReminderOut,
    ReminderUpdate,
)
from app.services.notifier import (
    EVENT_REMINDER_CREATED,
    EVENT_REMINDER_DELETED,
    EVENT_REMINDER_UPDATED,
    get_broker,
    mark_past_offsets_as_fired,
)

router = APIRouter(prefix="/reminders", tags=["reminders"], dependencies=[Depends(require_token)])


async def _load_tags_by_ids(session: AsyncSession, tag_ids: list[str]) -> list[Tag]:
    if not tag_ids:
        return []
    result = await session.execute(select(Tag).where(Tag.id.in_(tag_ids)))
    tags = list(result.scalars().all())
    found = {t.id for t in tags}
    missing = [tid for tid in tag_ids if tid not in found]
    if missing:
        raise HTTPException(422, f"unknown tag id(s): {missing}")
    return tags


async def _verify_group_id(session: AsyncSession, group_id: str | None) -> None:
    if group_id is None:
        return
    g = await session.get(Group, group_id)
    if g is None:
        raise HTTPException(422, f"unknown group id: {group_id}")


@router.get("", response_model=list[ReminderOut])
async def list_reminders(
    session: AsyncSession = Depends(db_session),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    status_: str | None = Query(None, alias="status"),
    kind: Literal["event", "deadline"] | None = Query(None),
    group_id: str | None = Query(None, description="empty string '__inbox__' = no group"),
    tag_id: str | None = Query(None, description="filter by tag id (single)"),
    include_cancelled: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
) -> list[ReminderOut]:
    stmt = select(Reminder)
    if from_:
        stmt = stmt.where(Reminder.target_at >= from_)
    if to:
        stmt = stmt.where(Reminder.target_at <= to)
    if status_:
        stmt = stmt.where(Reminder.status == status_)
    if kind:
        stmt = stmt.where(Reminder.kind == kind)
    if not include_cancelled:
        stmt = stmt.where(Reminder.status != ReminderStatus.CANCELLED.value)
    if group_id is not None:
        if group_id == "__inbox__":
            stmt = stmt.where(Reminder.group_id.is_(None))
        else:
            stmt = stmt.where(Reminder.group_id == group_id)
    if tag_id is not None:
        stmt = stmt.where(Reminder.tags.any(Tag.id == tag_id))
    stmt = stmt.order_by(Reminder.target_at.asc()).limit(limit)
    result = await session.execute(stmt)
    return [ReminderOut.model_validate(r) for r in result.scalars().unique().all()]


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    payload: ManualReminderCreate,
    session: AsyncSession = Depends(db_session),
) -> ReminderOut:
    if payload.kind == "deadline" and (
        payload.end_at is not None or payload.duration_minutes is not None
    ):
        raise HTTPException(422, "deadline must not have end_at or duration_minutes")

    await _verify_group_id(session, payload.group_id)
    tags = await _load_tags_by_ids(session, payload.tag_ids)

    # Manual create: respect explicit [] as "silent"; only fill defaults if field omitted
    offsets = payload.advance_reminders_minutes
    if offsets is None:
        from app.config import get_settings
        offsets = get_settings().default_offsets(payload.kind)

    reminder = Reminder(
        kind=payload.kind,
        title=payload.title,
        description=payload.description,
        target_at=payload.target_at,
        end_at=payload.end_at,
        duration_minutes=payload.duration_minutes,
        location=payload.location,
        participants=list(payload.participants),
        advance_reminders_minutes=list(offsets),
        fired_offsets=[],
        status=ReminderStatus.PENDING.value,
        source_text=payload.title,
        source_channel="manual",
        llm_model=None,
        extraction_group_id=None,
        group_id=payload.group_id,
    )
    reminder.tags = tags  # eager-set the relationship list
    mark_past_offsets_as_fired(reminder)
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    out = ReminderOut.model_validate(reminder)
    await get_broker().publish(EVENT_REMINDER_CREATED, out.model_dump(mode="json"))
    return out


@router.get("/{reminder_id}", response_model=ReminderOut)
async def get_reminder(
    reminder_id: str,
    session: AsyncSession = Depends(db_session),
) -> ReminderOut:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(404, "reminder not found")
    return ReminderOut.model_validate(reminder)


@router.put("/{reminder_id}", response_model=ReminderOut)
async def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    session: AsyncSession = Depends(db_session),
) -> ReminderOut:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(404, "reminder not found")

    data = payload.model_dump(exclude_unset=True)

    if "advance_reminders_minutes" in data and data["advance_reminders_minutes"] is not None:
        new_offsets = set(data["advance_reminders_minutes"])
        reminder.fired_offsets = [o for o in reminder.fired_offsets if o in new_offsets]

    new_end = data.get("end_at", reminder.end_at)
    new_dur = data.get("duration_minutes", reminder.duration_minutes)
    if reminder.kind == "deadline" and (new_end is not None or new_dur is not None):
        raise HTTPException(422, "deadline must not have end_at or duration_minutes")

    # Handle group_id update with FK verification
    if "group_id" in data:
        await _verify_group_id(session, data["group_id"])
        reminder.group_id = data["group_id"]
        del data["group_id"]

    # Handle tag_ids update with FK verification
    if "tag_ids" in data:
        tag_ids = data["tag_ids"]
        if tag_ids is None:
            # explicit None = no change (not allowed via this path; Pydantic dump excludes None on exclude_unset)
            pass
        else:
            reminder.tags = await _load_tags_by_ids(session, tag_ids)
        del data["tag_ids"]

    for key, value in data.items():
        setattr(reminder, key, value)

    await session.commit()
    await session.refresh(reminder)
    out = ReminderOut.model_validate(reminder)
    await get_broker().publish(EVENT_REMINDER_UPDATED, out.model_dump(mode="json"))
    return out


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_reminder(
    reminder_id: str,
    session: AsyncSession = Depends(db_session),
) -> Response:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(404, "reminder not found")
    reminder.status = ReminderStatus.CANCELLED.value
    await session.commit()
    await get_broker().publish(EVENT_REMINDER_DELETED, {"reminder_id": reminder_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{reminder_id}/done", response_model=ReminderOut)
async def mark_done(
    reminder_id: str,
    session: AsyncSession = Depends(db_session),
) -> ReminderOut:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(404, "reminder not found")
    reminder.status = ReminderStatus.DONE.value
    await session.commit()
    await session.refresh(reminder)
    out = ReminderOut.model_validate(reminder)
    await get_broker().publish(EVENT_REMINDER_UPDATED, out.model_dump(mode="json"))
    return out
