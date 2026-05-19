from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, require_token
from app.models import Group
from app.schemas import GroupCreate, GroupOut, GroupUpdate

router = APIRouter(prefix="/groups", tags=["groups"], dependencies=[Depends(require_token)])


@router.get("", response_model=list[GroupOut])
async def list_groups(session: AsyncSession = Depends(db_session)) -> list[GroupOut]:
    result = await session.execute(
        select(Group).order_by(Group.position.asc(), Group.created_at.asc())
    )
    return [GroupOut.model_validate(g) for g in result.scalars().all()]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate, session: AsyncSession = Depends(db_session)
) -> GroupOut:
    group = Group(
        name=payload.name.strip(),
        color=payload.color,
        position=payload.position,
    )
    session.add(group)
    try:
        await session.commit()
    except IntegrityError as e:
        raise HTTPException(409, "group name already exists") from e
    await session.refresh(group)
    return GroupOut.model_validate(group)


@router.put("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: str,
    payload: GroupUpdate,
    session: AsyncSession = Depends(db_session),
) -> GroupOut:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        group.name = data["name"].strip()
    if "color" in data:
        group.color = data["color"]
    if "position" in data and data["position"] is not None:
        group.position = data["position"]
    try:
        await session.commit()
    except IntegrityError as e:
        raise HTTPException(409, "group name already exists") from e
    await session.refresh(group)
    return GroupOut.model_validate(group)


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_group(
    group_id: str,
    session: AsyncSession = Depends(db_session),
) -> Response:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    # ON DELETE SET NULL on reminders.group_id handles the cascade
    await session.delete(group)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
