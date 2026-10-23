"""04C durable owner-scoped cancellation metadata; additive, no private content.

Upgrade is applied only to disposable test stores during engineering. Existing
local or hosted databases are never migrated by this implementation task.
"""
from alembic import op
import sqlalchemy as sa

revision = "0048_agent_run_controls"
down_revision = "0047_workspace_ownership_transfers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("agent_run_controls",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("settled", sa.Boolean(), nullable=False),
        sa.Column("deadline_epoch", sa.Float(), nullable=False),
        sa.CheckConstraint("status IN ('running','cancelled','expired','completed','failed')", name="ck_agent_run_control_status"))
    op.create_index("ix_agent_run_controls_owner_user_id", "agent_run_controls", ["owner_user_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM agent_run_controls")):
        raise RuntimeError("Run controls must be deliberately retired before downgrade.")
    op.drop_index("ix_agent_run_controls_owner_user_id", table_name="agent_run_controls")
    op.drop_table("agent_run_controls")
