"""Story / evidence bank service (Capstone P4/E3, §15/§16).

Turns approved candidate evidence into reusable interview stories. Provenance states are
explicit and truthful: a story built from source claims is SOURCE_BACKED (verified while
its claims live); editing its text marks it USER_CORRECTED; a freestanding story is
USER_CREATED. Story text is user- or deterministically-built from VERBATIM claim text —
this service invents no numbers, outcomes, dates, scope or awards (§16). No LLM call.
"""

from __future__ import annotations

from src.application.errors import ValidationError
from src.documents.repository import DocumentRepository, StoryRepository
from src.persistence import (
    STORY_SOURCE_BACKED,
    STORY_USER_CREATED,
    STORY_MODEL_SUGGESTED,
    STORY_USER_CORRECTED,
)

__all__ = ["StoriesApplicationService"]

_ALLOWED_STATUS = {STORY_SOURCE_BACKED, STORY_USER_CREATED, STORY_MODEL_SUGGESTED, STORY_USER_CORRECTED}
_TEXT_FIELDS = ("situation", "task", "action", "result")


class StoriesApplicationService:
    def __init__(self, *, stories: StoryRepository, documents: DocumentRepository) -> None:
        self._stories = stories
        self._documents = documents

    def create(self, *, user_id: int, title: str, status: str, fields: dict, claim_ids: list[int]) -> dict:
        if not (title or "").strip():
            raise ValidationError("A story needs a title.")
        if status not in _ALLOWED_STATUS:
            raise ValidationError("Unknown story status.")
        if status == STORY_SOURCE_BACKED and not claim_ids:
            raise ValidationError("A source-backed story needs at least one supporting claim.")
        clean = {k: (fields.get(k) or None) for k in _TEXT_FIELDS}
        comps = fields.get("competencies")
        clean["competencies"] = [str(c)[:120] for c in comps][:20] if isinstance(comps, list) else None
        story_id = self._stories.create(
            user_id=user_id, title=title.strip()[:255], status=status, fields=clean,
            claim_ids=[int(c) for c in claim_ids],
        )
        return self._stories.get(user_id=user_id, story_id=story_id)

    def draft_from_claims(self, *, user_id: int, title: str, claim_ids: list[int]) -> dict:
        """Deterministically draft a SOURCE_BACKED story from the user's OWN claims.

        Uses only the claims' verbatim (or user-corrected) text; invents nothing. Grouped
        into STAR fields by claim type. The result is fully editable by the candidate.
        """
        # Resolve each claim through owner-scoped document reads (cross-user impossible).
        selected = self._owned_claims(user_id, claim_ids)
        if not selected:
            raise ValidationError("Select at least one of your own claims.")
        situation = "; ".join(c["display_text"] for c in selected if c["claim_type"] == "experience")
        result = "; ".join(c["display_text"] for c in selected if c["claim_type"] == "achievement")
        comps = [c["display_text"] for c in selected if c["claim_type"] == "skill"][:20]
        fields = {
            "situation": situation or None,
            "task": None,
            "action": "; ".join(c["display_text"] for c in selected if c["claim_type"] not in ("skill",)) or None,
            "result": result or None,
            "competencies": comps or None,
        }
        story_id = self._stories.create(
            user_id=user_id, title=(title or "Untitled story").strip()[:255],
            status=STORY_SOURCE_BACKED, fields=fields, claim_ids=[c["id"] for c in selected],
        )
        return self._stories.get(user_id=user_id, story_id=story_id)

    def _owned_claims(self, user_id: int, claim_ids: list[int]) -> list[dict]:
        wanted = {int(c) for c in claim_ids}
        found: list[dict] = []
        for doc in self._documents.list_documents(user_id):
            detail = self._documents.get_document(user_id=user_id, document_id=doc["id"])
            for c in (detail or {}).get("claims", []):
                if c["id"] in wanted and c["review_state"] != "rejected":
                    found.append(c)
        return found

    def list(self, user_id: int) -> list[dict]:
        return self._stories.list(user_id)

    def get(self, *, user_id: int, story_id: int) -> dict | None:
        return self._stories.get(user_id=user_id, story_id=story_id)

    def update(self, *, user_id: int, story_id: int, fields: dict) -> dict | None:
        clean = {k: fields[k] for k in _TEXT_FIELDS if k in fields}
        if "title" in fields and (fields["title"] or "").strip():
            clean["title"] = fields["title"].strip()[:255]
        if "competencies" in fields and isinstance(fields["competencies"], list):
            clean["competencies"] = [str(c)[:120] for c in fields["competencies"]][:20]
        if not clean:
            raise ValidationError("Nothing to update.")
        # Editing a source-backed story's text makes it USER_CORRECTED (not verbatim source).
        return self._stories.update(user_id=user_id, story_id=story_id, fields=clean, mark_corrected=True)

    def delete(self, *, user_id: int, story_id: int) -> bool:
        return self._stories.delete(user_id=user_id, story_id=story_id)
