"""Candidate Evidence specialist — DETERMINISTIC, owner-scoped (Capstone P5, §8/§9/§28).

Selects and ranks a bounded set of the OWNER's APPROVED evidence (accepted/edited
claims and verified/user-authored stories) for a stated need, by transparent keyword
overlap. It uses NO model (per the E4 policy, SPECIALIST_EVIDENCE_ANALYSIS declares
``capability=NONE``), which makes it injection-inert and privacy-safe:
- the ``user_id`` is a trusted argument, never model-supplied;
- evidence comes only through the owner-scoped :class:`EvidenceAccessService`;
- rejected / unreviewed claims, source-revoked stories and model-suggested drafts are
  excluded upstream and never surface here;
- raw uploaded documents are never read (documents are untrusted DATA — P4).

It has NO side effects: it reads evidence, ranks it, and returns a safe projection.
"""

from __future__ import annotations

from src.agent.specialists._matching import overlap_score, tokens
from src.agent.specialists.schemas import EvidenceItem, EvidenceRequest, EvidenceSelection

__all__ = ["run_evidence_specialist"]

# Absolute bound on how many candidate evidence rows we ever consider (defence in
# depth against an unusually large evidence bank; the request.limit bounds the output).
_MAX_CONSIDERED = 200


def run_evidence_specialist(
    request: EvidenceRequest, *, user_id: int | str | None, evidence_service
) -> EvidenceSelection:
    """Return a bounded, owner-scoped selection of approved evidence for the need.

    Never raises into the caller: a missing owner / unavailable evidence service / any
    read failure degrades to an empty selection with a safe note.
    """
    if user_id is None or evidence_service is None:
        return EvidenceSelection(notes=["No candidate evidence was available."])
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return EvidenceSelection(notes=["No candidate evidence was available."])

    claims = list(evidence_service.approved_claims(uid))[:_MAX_CONSIDERED]
    stories = list(evidence_service.evidence_stories(uid))[:_MAX_CONSIDERED]

    comps = [c.strip() for c in (request.competencies or []) if c and c.strip()]
    need_tokens = tokens(request.need) | {t for c in comps for t in tokens(c)}

    scored: list[tuple[int, int, EvidenceItem]] = []  # (score, -tiebreak, item)

    for c in claims:
        text = c.get("display_text") or c.get("text") or ""
        score = overlap_score(need_tokens, text) if need_tokens else 1
        # A claim with no query still counts (score 1) so a bare "find my evidence"
        # returns something; a query boosts the relevant ones deterministically.
        prov = _claim_provenance(c)
        item = EvidenceItem(
            kind="claim", id=int(c["id"]),
            label=(c.get("claim_type") or "claim"),
            text=text[:1200],
            provenance=prov,
            competencies=[c.get("claim_type")] if c.get("claim_type") else [],
        )
        scored.append((score, int(c["id"]), item))

    for st in stories:
        blob = " ".join(
            str(st.get(k) or "") for k in ("title", "situation", "task", "action", "result")
        )
        story_comps = [str(x) for x in (st.get("competencies") or [])]
        score = overlap_score(need_tokens, blob + " " + " ".join(story_comps)) if need_tokens else 1
        item = EvidenceItem(
            kind="story", id=int(st["id"]),
            label=(st.get("title") or "story")[:200],
            text=(st.get("result") or st.get("situation") or st.get("action") or "")[:1200],
            provenance=f"story:{st.get('status')}/{st.get('evidence_state')}",
            competencies=story_comps[:30],
        )
        scored.append((score, int(st["id"]), item))

    # Deterministic order: score desc, then id asc for a stable tiebreak.
    scored.sort(key=lambda t: (-t[0], t[1]))
    selected = [item for score, _id, item in scored if score > 0][: request.limit]

    covered, uncovered = _competency_coverage(comps, selected)
    return EvidenceSelection(
        items=selected,
        covered_competencies=covered,
        uncovered_competencies=uncovered,
        claim_count=sum(1 for i in selected if i.kind == "claim"),
        story_count=sum(1 for i in selected if i.kind == "story"),
        notes=[] if selected else ["No approved evidence matched this need."],
    )


def _claim_provenance(claim: dict) -> str:
    section = claim.get("source_section")
    page = claim.get("source_page")
    state = claim.get("review_state") or "approved"
    where = section or (f"page {page}" if page is not None else "document")
    return f"claim:{state} ({where})"


def _competency_coverage(
    competencies: list[str], items: list[EvidenceItem]
) -> tuple[list[str], list[str]]:
    """Which requested competencies are supported by at least one selected item."""
    covered: list[str] = []
    uncovered: list[str] = []
    for comp in competencies:
        ctoks = tokens(comp)
        hit = any(
            overlap_score(ctoks, i.text) > 0
            or overlap_score(ctoks, " ".join(i.competencies)) > 0
            or overlap_score(ctoks, i.label) > 0
            for i in items
        )
        (covered if hit else uncovered).append(comp)
    return covered, uncovered
