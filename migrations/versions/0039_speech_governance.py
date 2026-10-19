"""Admin-governed server-side speech configuration (W12.4E). Additive: one table, nothing seeded.

``speech_governance`` holds one row per environment of SELECTION and POLICY for the server-side speech providers (provider choice from a code-defined list, enabled flags, the eligible subset of the seven
product speech languages, browser-fallback permissions and bounded timeouts). It holds no secret, path, command or endpoint. A missing row means the code defaults (providers selected, everything DISABLED).
The downgrade is FAIL-CLOSED: it refuses while any row exists, because that row is the only record of an administrator's speech decisions. Chains from 0038. Single head.

Revision ID: 0039_speech_governance
Revises: 0038_compensation_concepts
Create Date: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039_speech_governance"
down_revision = "0038_compensation_concepts"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "speech_governance",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("environment", sa.String(length=12), nullable=False),
        sa.Column("stt_provider", sa.String(length=24), nullable=False), sa.Column("tts_provider", sa.String(length=24), nullable=False),
        sa.Column("stt_enabled", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("tts_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("browser_stt_allowed", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("browser_tts_allowed", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("stt_timeout_seconds", sa.Integer(), server_default="30", nullable=False), sa.Column("tts_timeout_seconds", sa.Integer(), server_default="30", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reason", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("environment", name="uq_speech_governance_env"),
        sa.CheckConstraint(_in("environment", ("development", "staging", "production")), name="ck_sg_env"),
        sa.CheckConstraint(_in("stt_provider", ("openai_whisper",)), name="ck_sg_stt_provider"),
        sa.CheckConstraint(_in("tts_provider", ("kyutai_pocket_tts",)), name="ck_sg_tts_provider"),
        sa.CheckConstraint("stt_timeout_seconds BETWEEN 5 AND 120", name="ck_sg_stt_timeout"),
        sa.CheckConstraint("tts_timeout_seconds BETWEEN 5 AND 60", name="ck_sg_tts_timeout"),
        sa.CheckConstraint("revision >= 1", name="ck_sg_revision"),
    )


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any speech governance row exists."""
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM speech_governance")).scalar() or 0
    if count:
        raise RuntimeError(f"Refusing to downgrade 0039_speech_governance: {count} row(s) exist and are the only record of administrator speech decisions. Export or remove them deliberately first.")
    op.drop_table("speech_governance")
