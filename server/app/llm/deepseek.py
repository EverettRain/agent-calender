from __future__ import annotations

import time

from openai import AsyncOpenAI

from app.config import get_settings
from app.llm.adapter import LLMCallResult


class DeepSeekAdapter:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
    ) -> LLMCallResult:
        start = time.perf_counter()
        resp = await self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = resp.choices[0].message.content or ""
        usage = resp.usage
        return LLMCallResult(
            raw_text=content,
            model=resp.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
        )
