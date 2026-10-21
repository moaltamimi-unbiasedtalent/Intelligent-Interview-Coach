"""Knowledge health alert categories (package 02A). Additive and data-preserving: the CHECK on ``admin_notifications.category`` accepts four more code-defined
categories (``knowledge_collection_lost``, ``knowledge_source_files_missing``, ``knowledge_identity_mismatch``, ``knowledge_embedding_mismatch``). No table, column or row
is added or changed. It is the ONLY schema change of package 02A and exists because the in-app alert mechanism pins its categories in a database constraint.

The downgrade is FAIL-CLOSED: it refuses (deleting nothing) while any alert row uses one of the new categories, because restoring the narrower constraint would either
fail or force their deletion. Resolve and remove those alerts deliberately first. Chains from 0039. Single head.

Revision ID: 0040_knowledge_alert_categories
Revises: 0039_speech_governance
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040_knowledge_alert_categories"
down_revision = "0039_speech_governance"
branch_labels = None
depends_on = None

OLD = ("auth_failure_burst", "admin_access_denied_burst", "job_failed")
NEW_ONLY = ("knowledge_collection_lost", "knowledge_source_files_missing", "knowledge_identity_mismatch", "knowledge_embedding_mismatch")


def _in(values: tuple[str, ...]) -> str:
    return f"category IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    with op.batch_alter_table("admin_notifications") as b:
        b.drop_constraint("ck_notification_category", type_="check")
        b.create_check_constraint("ck_notification_category", _in(OLD + NEW_ONLY))


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any alert uses a knowledge category."""
    bind = op.get_bind()
    count = bind.execute(sa.text(f"SELECT COUNT(*) FROM admin_notifications WHERE category IN ({', '.join(repr(v) for v in NEW_ONLY)})")).scalar() or 0
    if count:
        raise RuntimeError(f"Refusing to downgrade 0040_knowledge_alert_categories: {count} knowledge alert row(s) exist. Resolve and remove them deliberately first.")
    with op.batch_alter_table("admin_notifications") as b:
        b.drop_constraint("ck_notification_category", type_="check")
        b.create_check_constraint("ck_notification_category", _in(OLD))
