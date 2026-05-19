"""tags + groups + reminder.group_id + reminder_tags M2M

Revision ID: 0002_tags_groups
Revises: 0001_initial
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "0002_tags_groups"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    op.create_table(
        "groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_groups_name", "groups", ["name"], unique=True)

    op.create_table(
        "reminder_tags",
        sa.Column(
            "reminder_id",
            sa.String(length=36),
            sa.ForeignKey("reminders.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.String(length=36),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_reminder_tags_reminder_id", "reminder_tags", ["reminder_id"]
    )
    op.create_index("ix_reminder_tags_tag_id", "reminder_tags", ["tag_id"])

    # Use batch mode so SQLite can ALTER properly
    with op.batch_alter_table("reminders") as batch:
        batch.add_column(sa.Column("group_id", sa.String(length=36), nullable=True))
        batch.create_index(
            "ix_reminders_group_id", ["group_id"]
        )
        batch.create_foreign_key(
            "fk_reminders_group_id",
            "groups",
            ["group_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("reminders") as batch:
        batch.drop_constraint("fk_reminders_group_id", type_="foreignkey")
        batch.drop_index("ix_reminders_group_id")
        batch.drop_column("group_id")

    op.drop_index("ix_reminder_tags_tag_id", table_name="reminder_tags")
    op.drop_index("ix_reminder_tags_reminder_id", table_name="reminder_tags")
    op.drop_table("reminder_tags")

    op.drop_index("ix_groups_name", table_name="groups")
    op.drop_table("groups")

    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_table("tags")
