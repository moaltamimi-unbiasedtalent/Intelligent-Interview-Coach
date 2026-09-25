"""Complete application-controlled account deletion (Capstone P8, §14/§15).

A single orchestrator that removes (or anonymizes) every user-owned resource the APPLICATION
controls, in child→parent order, then purges external resources (private files, agent
checkpoints). It is authenticated + owner-scoped at the call site, idempotent, and audited.

Design decisions (see docs/capstone/p8_e8_productisation_hosting.md):
- **Explicit deletes, not DB cascade.** SQLite does not enable FK cascades and several tables
  are not ORM-cascaded from ``User``, so we delete each table explicitly and owner-scoped.
- **Workspaces owned by the deleted user**: ownership is TRANSFERRED to another active member
  where one exists (oldest other active member, promoted to owner); otherwise the workspace and
  its dependents are deleted. Co-members are never silently stripped without a successor.
- **Audit is anonymized, not deleted** (security retention): ``actor_user_id`` → NULL, and a
  final ``account.deleted`` event is recorded.
- **Backups**: this removes live application data only. Historical hosting backups follow the
  provider's retention and are documented separately (§34) — never claimed as instantly erased.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select, update

from src import persistence as P


@dataclass
class DeletionSummary:
    user_id: int
    existed: bool
    deleted_rows: dict[str, int] = field(default_factory=dict)
    files_purged: int = 0
    files_failed: int = 0
    checkpoints_purged: int = 0
    workspaces_transferred: int = 0
    workspaces_deleted: int = 0
    audit_anonymized: int = 0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id, "existed": self.existed,
            "deleted_rows": self.deleted_rows, "files_purged": self.files_purged,
            "files_failed": self.files_failed, "checkpoints_purged": self.checkpoints_purged,
            "workspaces_transferred": self.workspaces_transferred,
            "workspaces_deleted": self.workspaces_deleted,
            "audit_anonymized": self.audit_anonymized,
        }


class AccountDeletionService:
    """Orchestrates the full cascade over one shared session factory + external stores."""

    def __init__(self, session_factory, *, document_store=None, agent_service=None,
                 audit_repository=None) -> None:
        self._sf = session_factory
        self._store = document_store
        self._agent = agent_service
        self._audit = audit_repository

    # -- external-resource discovery (collected inside the txn, purged after commit) --
    def _collect_storage_keys(self, s, user_id: int) -> list[str]:
        rows = s.execute(
            select(P.DocumentVersion.storage_key)
            .join(P.CandidateDocument, P.DocumentVersion.document_id == P.CandidateDocument.id)
            .where(P.CandidateDocument.user_id == user_id)
        ).all()
        return [r[0] for r in rows if r[0]]

    def _collect_run_ids(self, s, user_id: int) -> list[str]:
        rows = s.execute(
            select(P.PreparationMemory.source_run_id)
            .where(P.PreparationMemory.user_id == user_id,
                   P.PreparationMemory.source_run_id.is_not(None))
        ).all()
        return sorted({r[0] for r in rows if r[0]})

    def _handle_owned_workspaces(self, s, user_id: int, summary: DeletionSummary) -> None:
        owned = s.execute(
            select(P.Workspace).where(P.Workspace.owner_user_id == user_id)
        ).scalars().all()
        for ws in owned:
            successor = s.execute(
                select(P.WorkspaceMembership)
                .where(P.WorkspaceMembership.workspace_id == ws.id,
                       P.WorkspaceMembership.user_id != user_id,
                       P.WorkspaceMembership.status == P.MEMBERSHIP_STATUS_ACTIVE)
                .order_by(P.WorkspaceMembership.created_at.asc())
            ).scalars().first()
            if successor is not None:
                ws.owner_user_id = successor.user_id
                successor.role = P.WORKSPACE_ROLE_OWNER
                summary.workspaces_transferred += 1
            else:
                # No successor → delete the workspace and its dependents (explicit for SQLite).
                for model, col in (
                    (P.ShareGrant, P.ShareGrant.workspace_id),
                    (P.WorkspaceInvitation, P.WorkspaceInvitation.workspace_id),
                    (P.WorkspaceMembership, P.WorkspaceMembership.workspace_id),
                ):
                    for obj in s.execute(select(model).where(col == ws.id)).scalars().all():
                        s.delete(obj)
                s.delete(ws)
                summary.workspaces_deleted += 1

    def _delete_where(self, s, model, condition, summary: DeletionSummary, label: str) -> None:
        objs = s.execute(select(model).where(condition)).scalars().all()
        for obj in objs:
            s.delete(obj)
        if objs:
            summary.deleted_rows[label] = summary.deleted_rows.get(label, 0) + len(objs)

    def delete_account(self, user_id: int) -> DeletionSummary:
        """Remove/anonymize everything the application controls for ``user_id``. Idempotent."""
        summary = DeletionSummary(user_id=user_id, existed=False)
        storage_keys: list[str] = []
        run_ids: list[str] = []

        with self._sf() as s:
            user = s.get(P.User, user_id)
            if user is None:
                return summary  # already gone — no-op, idempotent
            summary.existed = True

            storage_keys = self._collect_storage_keys(s, user_id)
            run_ids = self._collect_run_ids(s, user_id)

            # 1) Workspaces owned by the user (transfer or delete) BEFORE deleting memberships.
            self._handle_owned_workspaces(s, user_id, summary)

            # 2) Memberships/invitations/shares where the user is a member/inviter/owner.
            self._delete_where(s, P.ShareGrant, P.ShareGrant.owner_user_id == user_id,
                               summary, "share_grants")
            self._delete_where(s, P.WorkspaceMembership,
                               P.WorkspaceMembership.user_id == user_id, summary, "memberships")
            self._delete_where(s, P.WorkspaceInvitation,
                               P.WorkspaceInvitation.inviter_user_id == user_id,
                               summary, "invitations_sent")
            # Invitations the user ACCEPTED: anonymize the accepted_user_id (SET NULL semantics).
            s.execute(update(P.WorkspaceInvitation)
                      .where(P.WorkspaceInvitation.accepted_user_id == user_id)
                      .values(accepted_user_id=None))

            # 3) Story bank → documents (children first).
            story_ids = [r[0] for r in s.execute(
                select(P.CandidateStory.id).where(P.CandidateStory.user_id == user_id)).all()]
            if story_ids:
                self._delete_where(s, P.StoryEvidence,
                                   P.StoryEvidence.story_id.in_(story_ids), summary,
                                   "story_evidence")
            self._delete_where(s, P.CandidateStory, P.CandidateStory.user_id == user_id,
                               summary, "stories")
            self._delete_where(s, P.DocumentClaim, P.DocumentClaim.user_id == user_id,
                               summary, "document_claims")
            doc_ids = [r[0] for r in s.execute(
                select(P.CandidateDocument.id)
                .where(P.CandidateDocument.user_id == user_id)).all()]
            if doc_ids:
                self._delete_where(s, P.DocumentVersion,
                                   P.DocumentVersion.document_id.in_(doc_ids), summary,
                                   "document_versions")
            self._delete_where(s, P.CandidateDocument,
                               P.CandidateDocument.user_id == user_id, summary, "documents")

            # 4) Interviews → questions → answers/reports (children first), + durable sessions.
            interview_ids = [r[0] for r in s.execute(
                select(P.Interview.id).where(P.Interview.user_id == user_id)).all()]
            if interview_ids:
                q_ids = [r[0] for r in s.execute(
                    select(P.Question.id)
                    .where(P.Question.interview_id.in_(interview_ids))).all()]
                if q_ids:
                    self._delete_where(s, P.Answer, P.Answer.question_id.in_(q_ids),
                                       summary, "answers")
                    self._delete_where(s, P.Question, P.Question.id.in_(q_ids),
                                       summary, "questions")
                self._delete_where(s, P.Report,
                                   P.Report.interview_id.in_(interview_ids), summary, "reports")
            self._delete_where(s, P.Interview, P.Interview.user_id == user_id,
                               summary, "interviews")
            self._delete_where(s, P.InterviewSession,
                               P.InterviewSession.user_id == user_id, summary,
                               "interview_sessions")

            # 5) Memory + feedback.
            self._delete_where(s, P.PreparationMemory,
                               P.PreparationMemory.user_id == user_id, summary, "memories")
            self._delete_where(s, P.UserFeedback, P.UserFeedback.user_id == user_id,
                               summary, "feedback")

            # 6) Identity/auth/prefs/entitlement (small owned rows).
            for model, col, label in (
                (P.AuthSession, P.AuthSession.user_id, "sessions"),
                (P.AuthToken, P.AuthToken.user_id, "tokens"),
                (P.AccountIdentity, P.AccountIdentity.user_id, "identities"),
                (P.PasswordCredential, P.PasswordCredential.user_id, "credential"),
                (P.ProductEntitlement, P.ProductEntitlement.user_id, "entitlement"),
                (P.UserPreference, P.UserPreference.user_id, "preferences"),
            ):
                self._delete_where(s, model, col == user_id, summary, label)

            # 7) Audit: anonymize (retain for security), do NOT delete.
            res = s.execute(update(P.AuditEvent)
                            .where(P.AuditEvent.actor_user_id == user_id)
                            .values(actor_user_id=None))
            summary.audit_anonymized = int(res.rowcount or 0)

            # 8) The user row last.
            s.delete(user)
            s.commit()

        # --- external resources (outside the DB txn) ---
        if self._store is not None:
            for key in storage_keys:
                try:
                    self._store.delete(key)
                    summary.files_purged += 1
                except Exception:  # noqa: BLE001 - best-effort; report failures honestly
                    summary.files_failed += 1

        if self._agent is not None and run_ids:
            for run_id in run_ids:
                try:
                    if self._agent.delete_run(run_id, str(user_id)):
                        summary.checkpoints_purged += 1
                except Exception:  # noqa: BLE001 - checkpoint purge is best-effort
                    pass

        # Final audit record (actor already anonymized; log the deletion itself).
        if self._audit is not None:
            try:
                self._audit.record(event_type="account.deleted", actor_user_id=None,
                                   target_type="user", target_id=str(user_id),
                                   context={"files_purged": summary.files_purged,
                                            "checkpoints_purged": summary.checkpoints_purged})
            except Exception:  # noqa: BLE001
                pass

        return summary
