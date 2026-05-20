"""app_settings single-row runtime config

Revision ID: 0003_app_settings
Revises: 0002_tags_groups
Create Date: 2026-05-21

"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "0003_app_settings"
down_revision: str | None = "0002_tags_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generate_model", sa.String(length=64), nullable=True),
        sa.Column("verify_model", sa.String(length=64), nullable=True),
        sa.Column("verify_enabled", sa.Boolean(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=True),
        sa.Column("token_budget", sa.Integer(), nullable=True),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
