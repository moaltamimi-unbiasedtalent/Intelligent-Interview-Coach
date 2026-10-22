"""Story / evidence bank service (Capstone P4/E3, §15/§16; completed by package 04A, REQ-OWN-06).

Turns approved candidate evidence into reusable interview stories. Provenance states are
explicit and truthful: a story built from source claims is SOURCE_BACKED (verified while
its claims live); editing its text marks it USER_CORRECTED; a freestanding story is
USER_CREATED. Story text is user- or deterministically-built from VERBATIM claim text —
this service invents no numbers, outcomes, dates, scope or awards (§16). No LLM call.

04A adds, all owner-scoped and deterministic: archive/restore, search/filter/tags, the Opportunity
link, evidence attach/detach (document claims and the candidate's own practice answers), the
candidate's self-confirmation (never presented as evidence), deterministic suggestions that need
the candidate's approval, and a bounded VIEW projection for sharing.
"""

from __future__ import annotations

import re
from typing import Callable

from src.application.errors import ValidationError
from src.documents.repository import STORY_BLOCK_CLOSE, STORY_BLOCK_OPEN, DocumentRepository, StoryRepository
from src.persistence import (
    STORY_MODEL_SUGGESTED,
    STORY_SOURCE_BACKED,
    STORY_USER_CORRECTED,
    STORY_USER_CREATED,
)

__all__ = ["StoriesApplicationService", "shared_projection", "compose_story_blocks", "MAX_TAGS", "MAX_TAG_CHARS", "MAX_SUGGEST_TERMS"]

_ALLOWED_STATUS = {STORY_SOURCE_BACKED, STORY_USER_CREATED, STORY_MODEL_SUGGESTED, STORY_USER_CORRECTED}
_TEXT_FIELDS = ("situation", "task", "action", "result")
MAX_TAGS = 20
MAX_TAG_CHARS = 60
MAX_SUGGEST_TERMS = 20
_ARCHIVE_FILTERS = ("active", "archived", "all")
_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)
_STOP = frozenset({"the", "and", "for", "with", "that", "this", "from", "have", "des", "und", "der", "die", "das", "les", "les", "pour", "una", "los", "las", "per", "com", "voor", "een"})

# opportunity_lookup(user_id, opportunity_id) -> {"target_role": str, ...} | None   (owner-scoped; None = not owned / missing)
OpportunityLookup = Callable[[int, int], "dict | None"]


def _tokens(text: str) -> set[str]:
    return {w for w in (m.group(0).lower() for m in _WORD.finditer(text or "")) if w not in _STOP}


def _clean_tags(raw) -> list[str]:
    """Bounded, de-duplicated competency tags (case-insensitive), order preserved."""
    out: list[str] = []
    seen: set[str] = set()
    for c in raw or []:
        t = " ".join(str(c).split())[:MAX_TAG_CHARS]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:MAX_TAGS]


def shared_projection(story: dict) -> dict:
    """The bounded VIEW projection a workspace member receives for a shared story: the candidate's own STAR text, tags and the verification LABEL.

    Never claim/answer/document ids, the Opportunity link, usage or confirmation timestamps. An archived story is not viewable (None)."""
    if story.get("archived_at"):
        return None  # type: ignore[return-value]
    return {
        "id": story["id"], "title": story["title"], "situation": story["situation"], "task": story["task"], "action": story["action"],
        "result": story["result"], "competencies": story["competencies"], "status": story["status"],
        "verification": story["verification"], "updated_at": story["updated_at"],
    }


def compose_story_blocks(stories: list[dict], max_chars: int = 3200) -> str:
    """The Practice background block for explicitly selected stories: ATTRIBUTED (story id, title, how it is verified) and marked so a later delete can
    strip exactly this text. It is untrusted DATA downstream (injection-screened before any prompt), never an instruction.

    The whole block is bounded by ``max_chars`` (each story gets an equal share; its STAR fields are clipped to fit, the closing marker is always kept)."""
    if not stories:
        return ""
    share = max(300, max_chars // len(stories))
    parts: list[str] = []
    for st in stories:
        open_m, close_m = STORY_BLOCK_OPEN.format(id=st["id"]), STORY_BLOCK_CLOSE.format(id=st["id"])
        head = f"Candidate story \"{st['title'][:80]}\" (verification: {st['verification']}; the candidate's own account)"
        present = [f for f in _TEXT_FIELDS if (st.get(f) or "").strip()]
        room = share - len(open_m) - len(close_m) - len(head) - 4 * (len(present) + 2)
        per_field = max(40, room // max(1, len(present)))
        lines = [open_m, head]
        for f in present:
            text = " ".join(st[f].split())
            lines.append(f"{f.capitalize()}: {text[:per_field]}")
        lines.append(close_m)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


class StoriesApplicationService:
    def __init__(self, *, stories: StoryRepository, documents: DocumentRepository, opportunity_lookup: OpportunityLookup | None = None) -> None:
        self._stories = stories
        self._documents = documents
        self._lookup = opportunity_lookup

    # -- helpers ----------------------------------------------------------------

    def _check_opportunity(self, user_id: int, opportunity_id: int | None) -> None:
        if opportunity_id is None:
            return
        if self._lookup is None or self._lookup(user_id, opportunity_id) is None:
            raise ValidationError("That Opportunity is not available.")      # foreign and missing look the same

    # -- create / draft -----------------------------------------------------------

    def create(self, *, user_id: int, title: str, status: str, fields: dict, claim_ids: list[int], opportunity_id: int | None = None) -> dict:
        if not (title or "").strip():
            raise ValidationError("A story needs a title.")
        if status not in _ALLOWED_STATUS:
            raise ValidationError("Unknown story status.")
        if status == STORY_SOURCE_BACKED and not claim_ids:
            raise ValidationError("A source-backed story needs at least one supporting claim.")
        self._check_opportunity(user_id, opportunity_id)
        clean = {k: ((fields.get(k) or "").strip() or None) for k in _TEXT_FIELDS}
        clean["competencies"] = _clean_tags(fields.get("competencies")) or None
        story_id = self._stories.create(
            user_id=user_id, title=title.strip()[:255], status=status, fields=clean,
            claim_ids=[int(c) for c in claim_ids], opportunity_id=opportunity_id,
        )
        return self._stories.get(user_id=user_id, story_id=story_id)

    def draft_from_claims(self, *, user_id: int, title: str, claim_ids: list[int], opportunity_id: int | None = None) -> dict:
        """Deterministically draft a SOURCE_BACKED story from the user's OWN claims.

        Uses only the claims' verbatim (or user-corrected) text; invents nothing. Grouped
        into STAR fields by claim type. The result is fully editable by the candidate.
        """
        # Resolve each claim through owner-scoped document reads (cross-user impossible).
        selected = self._owned_claims(user_id, claim_ids)
        if not selected:
            raise ValidationError("Select at least one of your own claims.")
        self._check_opportunity(user_id, opportunity_id)
        situation = "; ".join(c["display_text"] for c in selected if c["claim_type"] == "experience")
        result = "; ".join(c["display_text"] for c in selected if c["claim_type"] == "achievement")
        comps = [c["display_text"] for c in selected if c["claim_type"] == "skill"][:MAX_TAGS]
        fields = {
            "situation": situation or None,
            "task": None,
            "action": "; ".join(c["display_text"] for c in selected if c["claim_type"] not in ("skill",)) or None,
            "result": result or None,
            "competencies": _clean_tags(comps) or None,
        }
        story_id = self._stories.create(
            user_id=user_id, title=(title or "Untitled story").strip()[:255],
            status=STORY_SOURCE_BACKED, fields=fields, claim_ids=[c["id"] for c in selected], opportunity_id=opportunity_id,
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

    # -- read / search --------------------------------------------------------------

    def list(self, user_id: int, *, q: str | None = None, tag: str | None = None, status: str | None = None, verification: str | None = None,
             opportunity_id: int | None = None, archived: str = "active") -> list[dict]:
        """Search and filter the caller's OWN stories. ``q``: every word must appear in the title, STAR text or tags (case-insensitive)."""
        if archived not in _ARCHIVE_FILTERS:
            raise ValidationError("Unknown archive filter.")
        rows = self._stories.list(user_id, archived=archived)
        words = [w for w in (q or "").lower().split() if w]
        tag_l = (tag or "").strip().lower()
        out = []
        for st in rows:
            if status and st["status"] != status:
                continue
            if verification and st["verification"] != verification:
                continue
            if opportunity_id is not None and st["opportunity_id"] != opportunity_id:
                continue
            if tag_l and tag_l not in {t.lower() for t in st["competencies"]}:
                continue
            if words:
                hay = " ".join([st["title"], *(st.get(f) or "" for f in _TEXT_FIELDS), *st["competencies"]]).lower()
                if not all(w in hay for w in words):
                    continue
            out.append(st)
        return out

    def tags(self, user_id: int) -> list[str]:
        """Distinct competency tags across the caller's active stories (for the filter control)."""
        seen: dict[str, str] = {}
        for st in self._stories.list(user_id):
            for t in st["competencies"]:
                seen.setdefault(t.lower(), t)
        return sorted(seen.values(), key=str.lower)

    def get(self, *, user_id: int, story_id: int) -> dict | None:
        return self._stories.get(user_id=user_id, story_id=story_id)

    # -- edit / archive / confirm ------------------------------------------------------

    def update(self, *, user_id: int, story_id: int, fields: dict, opportunity_id: int | None = None, set_opportunity: bool = False) -> dict | None:
        clean: dict = {k: ((fields[k] or "").strip() or None) for k in _TEXT_FIELDS if k in fields}
        if "title" in fields and (fields["title"] or "").strip():
            clean["title"] = fields["title"].strip()[:255]
        if "competencies" in fields and isinstance(fields["competencies"], list):
            clean["competencies"] = _clean_tags(fields["competencies"])
        if set_opportunity:
            self._check_opportunity(user_id, opportunity_id)
            clean["opportunity_id"] = opportunity_id
        if not clean:
            raise ValidationError("Nothing to update.")
        # Editing a source-backed story's text makes it USER_CORRECTED (not verbatim source).
        return self._stories.update(user_id=user_id, story_id=story_id, fields=clean, mark_corrected=True)

    def archive(self, *, user_id: int, story_id: int) -> dict | None:
        return self._stories.set_archived(user_id=user_id, story_id=story_id, archived=True)

    def restore(self, *, user_id: int, story_id: int) -> dict | None:
        return self._stories.set_archived(user_id=user_id, story_id=story_id, archived=False)

    def confirm(self, *, user_id: int, story_id: int, confirmed: bool) -> dict | None:
        """The candidate attests the account is accurate. A self-attestation: it is labelled "self_confirmed", never "evidence_verified"."""
        return self._stories.set_confirmed(user_id=user_id, story_id=story_id, confirmed=confirmed)

    # -- evidence ------------------------------------------------------------------------

    def attach_evidence(self, *, user_id: int, story_id: int, kind: str, ref_id: int, allowed_interview_ids: list[int] | None = None) -> dict | None:
        if kind == "claim":
            return self._stories.attach_claim(user_id=user_id, story_id=story_id, claim_id=ref_id)
        if kind == "answer":
            return self._stories.attach_answer(user_id=user_id, story_id=story_id, answer_id=ref_id, allowed_interview_ids=allowed_interview_ids)
        raise ValidationError("Unknown evidence kind.")

    def answer_sources(self, *, user_id: int, allowed_interview_ids: list[int] | None) -> list[dict]:
        return self._stories.answer_sources(user_id, allowed_interview_ids)

    def detach_evidence(self, *, user_id: int, story_id: int, kind: str, ref_id: int) -> dict | None:
        if kind == "claim":
            return self._stories.detach_claim(user_id=user_id, story_id=story_id, claim_id=ref_id)
        if kind == "answer":
            return self._stories.detach_answer(user_id=user_id, story_id=story_id, answer_id=ref_id)
        raise ValidationError("Unknown evidence kind.")

    # -- suggestions -----------------------------------------------------------------------

    def suggest(self, *, user_id: int, terms: list[str], opportunity_id: int | None = None, limit: int = 5) -> list[dict]:
        """Rank the caller's OWN usable stories for an interview. Deterministic word/tag overlap; no model, no fabrication.

        A suggestion is only a proposal: nothing is used in Practice until the candidate explicitly selects it and consents (``requires_approval``)."""
        wanted = {t.lower() for t in _clean_tags(terms)[:MAX_SUGGEST_TERMS]}
        wanted_tokens: set[str] = set()
        for t in wanted:
            wanted_tokens |= _tokens(t)
        if opportunity_id is not None:
            opp = self._lookup(user_id, opportunity_id) if self._lookup else None
            if opp is None:
                raise ValidationError("That Opportunity is not available.")
            wanted_tokens |= _tokens(opp.get("target_role") or "")
        if not wanted_tokens and not wanted:
            return []
        ranked = []
        for st in self._stories.evidence_stories(user_id):
            tags = {t.lower() for t in st["competencies"]}
            tag_hits = sorted(tags & wanted | {t for t in tags if _tokens(t) & wanted_tokens})
            text_tokens = _tokens(" ".join([st["title"], *(st.get(f) or "" for f in _TEXT_FIELDS)]))
            word_hits = sorted(text_tokens & wanted_tokens)
            score = 3 * len(tag_hits) + len(word_hits)
            if opportunity_id is not None and st["opportunity_id"] == opportunity_id:
                score += 2
            if score <= 0:
                continue
            ranked.append((score, st, tag_hits, word_hits))
        ranked.sort(key=lambda r: (-r[0], r[1]["id"]))
        return [
            {"id": st["id"], "title": st["title"], "verification": st["verification"], "competencies": st["competencies"],
             "matched": (tag_hits + [w for w in word_hits if w not in tag_hits])[:6], "requires_approval": True}
            for _score, st, tag_hits, word_hits in ranked[:max(1, min(limit, 10))]
        ]

    # -- delete ----------------------------------------------------------------------------

    def delete(self, *, user_id: int, story_id: int) -> bool:
        return self._stories.delete(user_id=user_id, story_id=story_id)
