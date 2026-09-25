"""Owner-scoped approved-evidence access boundary (Capstone P5, §8/§9/§28).

The single, deliberately narrow surface through which a specialist may reach a
candidate's PRIVATE evidence. It exposes ONLY:
- APPROVED claims (review_state accepted/edited) — never pending/unreviewed/rejected;
- SAFE stories (source-backed & still verified, or user-authored) — never
  source-revoked or model-suggested drafts;
and NEVER raw uploaded documents or file bytes (documents are untrusted DATA and are
never placed in a prompt — see the P4 documents pipeline).

The ``user_id`` is always a trusted argument from run state; this service never accepts
a model-supplied user id, and every underlying repository read is itself owner-scoped,
so cross-user access is impossible even if a caller passed a wrong id.
"""

from __future__ import annotations

from src.documents.repository import DocumentRepository, StoryRepository

__all__ = ["EvidenceAccessService"]


class EvidenceAccessService:
    def __init__(self, *, documents: DocumentRepository, stories: StoryRepository) -> None:
        self._documents = documents
        self._stories = stories

    def approved_claims(self, user_id: int) -> list[dict]:
        """The owner's approved claims (safe dict projections). Empty on any failure."""
        try:
            return self._documents.approved_claims(int(user_id))
        except Exception:  # noqa: BLE001 - evidence is supplemental; never break a run
            return []

    def evidence_stories(self, user_id: int) -> list[dict]:
        """The owner's usable evidence stories (safe dict projections). Empty on failure."""
        try:
            return self._stories.evidence_stories(int(user_id))
        except Exception:  # noqa: BLE001
            return []
