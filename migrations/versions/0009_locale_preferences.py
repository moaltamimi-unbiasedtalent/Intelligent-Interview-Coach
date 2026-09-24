"""Locale preferences — interface + conversation language (Capstone P3.5).

Adds two INDEPENDENT, bounded language preferences to ``user_preferences``:
``interface_locale`` (UI language) and ``conversation_language`` (the language the
candidate wants Mo to use). Both default to English and are distinct from the P3
dictation locale and from the model profile. A language never changes labour-market
geography. Additive only; chains from 0008. Single head.

Revision ID: 0009_locale_preferences
Revises: 0008_user_preferences
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_locale_preferences"
down_revision = "0008_user_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("interface_locale", sa.String(length=8), nullable=False, server_default="en"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("conversation_language", sa.String(length=8), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "conversation_language")
    op.drop_column("user_preferences", "interface_locale")
