"""initial schema: reminders + extraction_attempts

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_at", UTCDateTime(), nullable=False),
        sa.Column("end_at", UTCDateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("advance_reminders_minutes", sa.JSON(), nullable=False),
        sa.Column("fired_offsets", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_channel", sa.String(length=32), nullable=False),
        sa.Column("llm_model", sa.String(length=64), nullable=True),
        sa.Column("extraction_group_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_reminders_kind", "reminders", ["kind"])
    op.create_index("ix_reminders_target_at", "reminders", ["target_at"])
    op.create_index("ix_reminders_status", "reminders", ["status"])
    op.create_index("ix_reminders_extraction_group_id", "reminders", ["extraction_group_id"])

    op.create_table(
        "extraction_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("extraction_group_id", sa.String(length=36), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("verify_pass", sa.Boolean(), nullable=True),
        sa.Column("verify_issues", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )
    op.create_index(
        "ix_extraction_attempts_extraction_group_id",
        "extraction_attempts",
        ["extraction_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_extraction_attempts_extraction_group_id", table_name="extraction_attempts")
    op.drop_table("extraction_attempts")
    op.drop_index("ix_reminders_extraction_group_id", table_name="reminders")
    op.drop_index("ix_reminders_status", table_name="reminders")
    op.drop_index("ix_reminders_target_at", table_name="reminders")
    op.drop_index("ix_reminders_kind", table_name="reminders")
    op.drop_table("reminders")
