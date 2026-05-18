from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class LLMCallResult:
    raw_text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class LLMAdapter(Protocol):
    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
    ) -> LLMCallResult:
        """Call chat completion with response_format=json_object and return raw JSON text."""
        ...
