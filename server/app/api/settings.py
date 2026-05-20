from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.deps import db_session, require_token
from app.models import AppSettings
from app.schemas import AppSettingsOut, AppSettingsUpdate
from app.services.runtime_config import get_app_settings_row, resolve_runtime_config

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_token)])


@router.get("", response_model=AppSettingsOut)
async def get_app_settings(
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> AppSettingsOut:
    cfg = await resolve_runtime_config(session, settings)
    return AppSettingsOut(
        generate_model=cfg.generate_model,
        verify_model=cfg.verify_model,
        verify_enabled=cfg.verify_enabled,
        max_attempts=cfg.max_attempts,
        token_budget=cfg.token_budget,
    )


@router.put("", response_model=AppSettingsOut)
async def update_app_settings(
    payload: AppSettingsUpdate,
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> AppSettingsOut:
    row = await get_app_settings_row(session)
    if row is None:
        row = AppSettings(id=1)
        session.add(row)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)

    await session.commit()

    cfg = await resolve_runtime_config(session, settings)
    return AppSettingsOut(
        generate_model=cfg.generate_model,
        verify_model=cfg.verify_model,
        verify_enabled=cfg.verify_enabled,
        max_attempts=cfg.max_attempts,
        token_budget=cfg.token_budget,
    )
