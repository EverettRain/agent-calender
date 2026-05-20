"""Effective runtime configuration: DB overrides on top of env defaults.

Model selection and extraction tunables can be changed at runtime via the
/settings API (persisted in the app_settings table). Where a DB value is NULL,
the env-based Settings default applies.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AppSettings


@dataclass(slots=True)
class RuntimeConfig:
    generate_model: str
    verify_model: str
    verify_enabled: bool
    max_attempts: int
    token_budget: int


async def get_app_settings_row(session: AsyncSession) -> AppSettings | None:
    result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
    return result.scalar_one_or_none()


async def resolve_runtime_config(session: AsyncSession, settings: Settings) -> RuntimeConfig:
    row = await get_app_settings_row(session)
    return RuntimeConfig(
        generate_model=(row.generate_model if row and row.generate_model else settings.DEEPSEEK_MODEL),
        verify_model=(row.verify_model if row and row.verify_model else settings.EXTRACTION_VERIFY_MODEL),
        verify_enabled=(
            row.verify_enabled
            if row and row.verify_enabled is not None
            else settings.EXTRACTION_VERIFY_ENABLED
        ),
        max_attempts=(
            row.max_attempts
            if row and row.max_attempts is not None
            else settings.EXTRACTION_MAX_ATTEMPTS
        ),
        token_budget=(
            row.token_budget
            if row and row.token_budget is not None
            else settings.EXTRACTION_TOKEN_BUDGET_PER_INGEST
        ),
    )
