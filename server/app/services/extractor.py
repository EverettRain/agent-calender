from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Literal

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.llm.adapter import LLMAdapter
from app.llm.prompts import build_extract_messages, build_verify_messages
from app.models import (
    AttemptStage,
    ExtractionAttempt,
    Reminder,
    ReminderStatus,
)
from app.schemas import GenerateResponse, ReminderDraft, VerifyResponse
from app.services.notifier import mark_past_offsets_as_fired

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class ExtractionResult:
    extraction_group_id: str
    status: Literal["success", "pending_review"]
    reminders: list[Reminder]
    attempts: int
    total_tokens: int


class ExtractorService:
    """Generate → schema validate → reverse-verify → retry pipeline."""

    def __init__(self, llm: LLMAdapter, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def extract(
        self,
        session: AsyncSession,
        text: str,
        source_channel: str,
    ) -> ExtractionResult:
        group_id = str(uuid.uuid4())
        attempt_no = 0
        total_tokens = 0
        last_valid_drafts: list[ReminderDraft] | None = None
        feedback_issues: list[str] | None = None
        prior_attempt_json: dict | None = None

        for _ in range(self._settings.EXTRACTION_MAX_ATTEMPTS):
            attempt_no += 1

            if total_tokens >= self._settings.EXTRACTION_TOKEN_BUDGET_PER_INGEST:
                log.warning(
                    "extract.token_budget_exceeded",
                    group_id=group_id,
                    total_tokens=total_tokens,
                )
                break

            # ===== ① Generate =====
            gen_messages = build_extract_messages(
                text,
                tz=self._settings.TZ,
                prior_attempt=prior_attempt_json,
                feedback_issues=feedback_issues,
            )
            try:
                gen_result = await self._llm.chat_json(
                    gen_messages, model=self._settings.DEEPSEEK_MODEL
                )
            except Exception as exc:  # network / api error
                session.add(
                    ExtractionAttempt(
                        extraction_group_id=group_id,
                        source_text=text,
                        attempt_no=attempt_no,
                        stage=AttemptStage.GENERATE.value,
                        model=self._settings.DEEPSEEK_MODEL,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                await session.flush()
                feedback_issues = [f"上次调用失败: {exc}"]
                continue

            total_tokens += gen_result.prompt_tokens + gen_result.completion_tokens

            # ===== ② Schema Validate =====
            parse_error: str | None = None
            drafts: list[ReminderDraft] | None = None
            try:
                raw_obj = json.loads(gen_result.raw_text)
                parsed = GenerateResponse.model_validate(raw_obj)
                drafts = parsed.reminders
            except (json.JSONDecodeError, ValidationError) as exc:
                parse_error = f"{type(exc).__name__}: {exc}"

            session.add(
                ExtractionAttempt(
                    extraction_group_id=group_id,
                    source_text=text,
                    attempt_no=attempt_no,
                    stage=AttemptStage.GENERATE.value,
                    model=gen_result.model,
                    prompt_tokens=gen_result.prompt_tokens,
                    completion_tokens=gen_result.completion_tokens,
                    latency_ms=gen_result.latency_ms,
                    result_json=gen_result.raw_text,
                    error=parse_error,
                )
            )
            await session.flush()

            if drafts is None:
                feedback_issues = [
                    f"上一次输出不是合法的 schema-conforming JSON: {parse_error}",
                    "请严格按照 schema 输出，不要包含额外字段，不要遗漏必填字段。",
                ]
                try:
                    prior_attempt_json = json.loads(gen_result.raw_text)
                except Exception:
                    prior_attempt_json = None
                continue

            last_valid_drafts = drafts
            prior_attempt_json = {
                "reminders": [d.model_dump(mode="json") for d in drafts]
            }

            # ===== ③ Reverse-Verify =====
            if not self._settings.EXTRACTION_VERIFY_ENABLED:
                return await self._persist_success(
                    session, text, source_channel, group_id, drafts, gen_result.model,
                    attempt_no, total_tokens,
                )

            if total_tokens >= self._settings.EXTRACTION_TOKEN_BUDGET_PER_INGEST:
                log.warning("extract.token_budget_exceeded_before_verify", group_id=group_id)
                break

            verify_messages = build_verify_messages(text, prior_attempt_json, tz=self._settings.TZ)
            verify_error: str | None = None
            verify_result_obj: VerifyResponse | None = None
            try:
                verify_result = await self._llm.chat_json(
                    verify_messages, model=self._settings.EXTRACTION_VERIFY_MODEL
                )
                total_tokens += verify_result.prompt_tokens + verify_result.completion_tokens

                try:
                    verify_obj = json.loads(verify_result.raw_text)
                    verify_result_obj = VerifyResponse.model_validate(verify_obj)
                except (json.JSONDecodeError, ValidationError) as exc:
                    verify_error = f"verify response invalid: {type(exc).__name__}: {exc}"
            except Exception as exc:
                verify_error = f"{type(exc).__name__}: {exc}"
                verify_result = None

            session.add(
                ExtractionAttempt(
                    extraction_group_id=group_id,
                    source_text=text,
                    attempt_no=attempt_no,
                    stage=AttemptStage.VERIFY.value,
                    model=(
                        verify_result.model if verify_result else self._settings.EXTRACTION_VERIFY_MODEL
                    ),
                    prompt_tokens=verify_result.prompt_tokens if verify_result else 0,
                    completion_tokens=verify_result.completion_tokens if verify_result else 0,
                    latency_ms=verify_result.latency_ms if verify_result else 0,
                    result_json=verify_result.raw_text if verify_result else None,
                    verify_pass=verify_result_obj.pass_ if verify_result_obj else None,
                    verify_issues=verify_result_obj.issues if verify_result_obj else None,
                    error=verify_error,
                )
            )
            await session.flush()

            if verify_error is not None or verify_result_obj is None:
                # treat as not-pass, but be conservative: accept the drafts if we've
                # already burned budget and verifier itself is broken
                feedback_issues = [verify_error or "verifier 输出无法解析"]
                continue

            if verify_result_obj.pass_:
                return await self._persist_success(
                    session, text, source_channel, group_id, drafts,
                    gen_result.model, attempt_no, total_tokens,
                )

            feedback_issues = verify_result_obj.issues or ["verifier 判定不通过但未给出具体问题"]

        # ===== Fallback: pending_review =====
        log.warning(
            "extract.fallback_pending_review",
            group_id=group_id,
            attempts=attempt_no,
            total_tokens=total_tokens,
            had_valid_drafts=last_valid_drafts is not None,
        )
        if last_valid_drafts is None:
            return ExtractionResult(
                extraction_group_id=group_id,
                status="pending_review",
                reminders=[],
                attempts=attempt_no,
                total_tokens=total_tokens,
            )
        reminders = self._drafts_to_reminders(
            last_valid_drafts,
            text=text,
            source_channel=source_channel,
            group_id=group_id,
            model=self._settings.DEEPSEEK_MODEL,
            status=ReminderStatus.PENDING_REVIEW,
        )
        for r in reminders:
            session.add(r)
        await session.flush()
        return ExtractionResult(
            extraction_group_id=group_id,
            status="pending_review",
            reminders=reminders,
            attempts=attempt_no,
            total_tokens=total_tokens,
        )

    async def _persist_success(
        self,
        session: AsyncSession,
        text: str,
        source_channel: str,
        group_id: str,
        drafts: list[ReminderDraft],
        model: str,
        attempt_no: int,
        total_tokens: int,
    ) -> ExtractionResult:
        reminders = self._drafts_to_reminders(
            drafts,
            text=text,
            source_channel=source_channel,
            group_id=group_id,
            model=model,
            status=ReminderStatus.PENDING,
        )
        for r in reminders:
            session.add(r)
        await session.flush()
        return ExtractionResult(
            extraction_group_id=group_id,
            status="success",
            reminders=reminders,
            attempts=attempt_no,
            total_tokens=total_tokens,
        )

    def _drafts_to_reminders(
        self,
        drafts: list[ReminderDraft],
        *,
        text: str,
        source_channel: str,
        group_id: str,
        model: str,
        status: ReminderStatus,
    ) -> list[Reminder]:
        out: list[Reminder] = []
        for d in drafts:
            offsets = d.advance_reminders_minutes
            # Treat None OR empty as "use default" — LLMs sometimes return [] lazily
            # even when the user didn't ask for silent. User can later PUT [] explicitly
            # via the reminders API if they truly want silent.
            if not offsets:
                offsets = self._settings.default_offsets(d.kind)
            reminder = Reminder(
                kind=d.kind,
                title=d.title,
                description=d.description,
                target_at=d.target_at,
                end_at=d.end_at,
                duration_minutes=d.duration_minutes,
                location=d.location,
                participants=list(d.participants),
                advance_reminders_minutes=list(offsets),
                fired_offsets=[],
                status=status.value,
                source_text=text,
                source_channel=source_channel,
                llm_model=model,
                extraction_group_id=group_id,
                group_id=None,
            )
            # Set tags eagerly so Pydantic can serialize without async-load
            reminder.tags = []
            # Already-past offsets: mark fired without retroactive notification
            mark_past_offsets_as_fired(reminder)
            out.append(reminder)
        return out
