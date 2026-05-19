from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, require_token
from app.models import Tag
from app.schemas import TagCreate, TagOut, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"], dependencies=[Depends(require_token)])


@router.get("", response_model=list[TagOut])
async def list_tags(session: AsyncSession = Depends(db_session)) -> list[TagOut]:
    result = await session.execute(select(Tag).order_by(Tag.name.asc()))
    return [TagOut.model_validate(t) for t in result.scalars().all()]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagCreate, session: AsyncSession = Depends(db_session)
) -> TagOut:
    tag = Tag(name=payload.name.strip(), color=payload.color)
    session.add(tag)
    try:
        await session.commit()
    except IntegrityError as e:
        raise HTTPException(409, "tag name already exists") from e
    await session.refresh(tag)
    return TagOut.model_validate(tag)


@router.put("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: str,
    payload: TagUpdate,
    session: AsyncSession = Depends(db_session),
) -> TagOut:
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "tag not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        tag.name = data["name"].strip()
    if "color" in data:
        tag.color = data["color"]
    try:
        await session.commit()
    except IntegrityError as e:
        raise HTTPException(409, "tag name already exists") from e
    await session.refresh(tag)
    return TagOut.model_validate(tag)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_tag(
    tag_id: str,
    session: AsyncSession = Depends(db_session),
) -> Response:
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "tag not found")
    await session.delete(tag)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
