"""Explainable evidence qualification (GKB-14). CATEGORICAL, never numerical: no confidence percentage exists because there is no validated model. The state is a VIEW over a resolution
(it duplicates no qualification authority: registry approval, measurement qualification and the resolution outcome stay where they are) and always lists the factors behind it.

States: SUFFICIENT_EVIDENCE, LIMITED_EVIDENCE, AMBIGUOUS, CONFLICTING, INSUFFICIENT_EVIDENCE. An EVIDENCE outcome is SUFFICIENT only when every factor is strong: a C1 national detailed figure for the exact occupation, a recorded basis, earnings concept, population and
method, an exact or restored official classification, no crosswalk of lesser qualification, no divergent corroboration and no pending precedence decision. Anything weaker is LIMITED and the weak factors are named. The state describes evidence QUALITY, not approval: it does not make a
figure operational. Freshness is reported as recorded (reference year, publication date, vintage); today's date is never substituted for a missing value and nothing is described as current market pay."""

from __future__ import annotations

from typing import Any

__all__ = ["EVIDENCE_STATES", "assess_evidence_state"]

EVIDENCE_STATES = ("SUFFICIENT_EVIDENCE", "LIMITED_EVIDENCE", "AMBIGUOUS", "CONFLICTING", "INSUFFICIENT_EVIDENCE")
_STRONG_CLASSIFICATION = {"known_key": "exact_code", "code_exact": "exact_code", "alias_exact": "alias_exact"}


def assess_evidence_state(resp, *, record_level: str | None = None, latest_available: bool | None = None) -> dict[str, Any]:
    outcome = resp.outcome.value
    if outcome == "ambiguous":
        return {"state": "AMBIGUOUS", "factors": {}, "weak_factors": ["occupation_identity_ambiguous"]}
    if outcome == "conflict":
        return {"state": "CONFLICTING", "factors": {}, "weak_factors": ["incompatible_or_disagreeing_evidence_preserved"]}
    if outcome != "evidence":
        return {"state": "INSUFFICIENT_EVIDENCE", "factors": {}, "weak_factors": [outcome]}
    grade = (resp.candidates[0].get("grade") if resp.candidates else None) or ""
    known = [resp.pay_basis != "unknown", resp.earnings_concept != "unknown", resp.population_scope != "unknown", resp.evidence_method != "unknown"]
    fb = resp.fallback or {}
    factors = {
        "source_authority": {"national_official_occupation_statistics": "national_official", "national_public_employment_service": "national_public_employment_service",
                             "eurostat_harmonised": "international_harmonised"}.get(resp.precedence_category or "", "other"),
        "occupation_specificity": resp.occupation_specificity or "unknown",
        "occupation_granularity": record_level or "unknown",
        "geographic_specificity": resp.geography_level or "unknown",
        "methodological_clarity": "clear" if all(known) else ("unclear" if not any(known) else "partial"),
        "freshness": "reference_year_and_publication_date_recorded" if (resp.freshness or {}).get("publication_date") else "reference_year_recorded_publication_date_unknown",
        "reference_year_is_latest_available": "yes" if latest_available else ("no" if latest_available is False else "unknown"),
        "classification_certainty": _STRONG_CLASSIFICATION.get(grade, "tolerant_or_weak"),
        "crosswalk_qualification": fb.get("qualification", "not_used"),
        "completeness": ("citation_and_bounds" if resp.citation and resp.lower_value is not None else ("citation_only" if resp.citation else "no_citation")),
        "corroboration": "divergent" if any(not c.get("agrees") for c in resp.corroborating) else ("agreeing" if resp.corroborating else "none"),
        "precedence_decision": "pending_owner_decision" if resp.precedence_pending else "settled",
    }
    weak = []
    if resp.evidence_class != "C1":
        weak.append(f"evidence_class_{(resp.evidence_class or 'unknown').lower()}")
    if factors["occupation_specificity"] != "exact":
        weak.append("occupation_not_exact")
    if factors["occupation_granularity"] != "detailed":
        weak.append("occupation_granularity_not_detailed")
    if factors["methodological_clarity"] != "clear":
        weak.append("methodology_incompletely_recorded")
    if factors["classification_certainty"] == "tolerant_or_weak":
        weak.append("occupation_classification_not_exact")
    if factors["crosswalk_qualification"] not in ("not_used", "operationally_approved", "licensed_for_runtime", "independently_reviewed"):
        weak.append("crosswalk_not_independently_reviewed")
    if factors["corroboration"] == "divergent":
        weak.append("corroborating_source_diverges")
    if factors["precedence_decision"] != "settled":
        weak.append("precedence_decision_pending")
    return {"state": "SUFFICIENT_EVIDENCE" if not weak else "LIMITED_EVIDENCE", "factors": factors, "weak_factors": weak}
