from __future__ import annotations

import hmac
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session_factory
from app.llm.adapter import LLMAdapter
from app.llm.deepseek import DeepSeekAdapter
from app.services.extractor import ExtractorService

_bearer = HTTPBearer(auto_error=False)


async def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    if not hmac.compare_digest(credentials.credentials, settings.API_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


async def db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Override hooks (used by tests)
_llm_override: LLMAdapter | None = None


def set_llm_override(adapter: LLMAdapter | None) -> None:
    global _llm_override
    _llm_override = adapter


def get_llm() -> LLMAdapter:
    if _llm_override is not None:
        return _llm_override
    return DeepSeekAdapter()


def get_extractor(
    settings: Settings = Depends(get_settings),
) -> ExtractorService:
    return ExtractorService(get_llm(), settings)
