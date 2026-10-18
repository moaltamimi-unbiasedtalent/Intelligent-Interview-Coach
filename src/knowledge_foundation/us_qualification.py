"""P10C-F2A-Q: deterministic US evidence qualification review, count reconciliation and curated-alias evidence rules. Pure functions over rows and database dictionaries; they write nothing
by themselves. Separation of duties (owner direction 2026-10-18):

* engineering validation: ``review_record`` produces a reproducible per-record outcome and reason. A record that passes every engineering rule may be moved to the EXISTING measurement state
  ``engineering_checked``; it is never moved to ``qualified`` here, because ``qualified`` needs a named human reviewer and no human reviewer exists in the isolated environment;
* statistical uncertainty is a separate dimension: BLS relative standard errors are preserved and described, never converted into a cutoff or a precision claim;
* curated aliases are PROPOSED from approved-source evidence only (the official SOC title rule below); similarity, popularity or model knowledge is never evidence.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from src.knowledge_foundation.us_sources import OEWS_EDITION, OEWS_SOURCE, SOC_EDITION, OewsRow, SocNode

__all__ = ["review_record", "REVIEW_OUTCOMES", "rse_distribution", "annual_only_reconciliation", "soc_title_candidates", "build_alias_proposals", "title_tokens"]

REVIEW_OUTCOMES = ("ENGINEERING_CHECKED", "PENDING_REVIEW", "INSUFFICIENT", "CONFLICTING", "QUARANTINED")
_PROVENANCE_KEYS = ("transformation", "manifest_file_id", "archive_sha256", "archive_member", "sheet", "source_rows", "source_field", "emp_prse", "tot_emp")


def review_record(rec: dict[str, Any], *, source: dict[str, Any], file_integrity_ok: bool, soc_level: str | None, key_count: int) -> tuple[str, list[str]]:
    """The deterministic engineering review of ONE stored OEWS observation. Returns (outcome, reasons). ``ENGINEERING_CHECKED`` means every rule below holds; it does not mean
    qualified, precise or approved. ``rec`` is the stored row view (``from_row``) plus its provenance."""
    why: list[str] = []
    prov = rec.get("provenance") or {}
    if rec["source_ref"] != OEWS_SOURCE or rec["source_edition"] != OEWS_EDITION:
        return "QUARANTINED", ["source_or_edition_not_the_authorised_one"]
    if key_count > 1:
        return "CONFLICTING", ["record_key_not_unique"]
    if source.get("approval_status") not in ("approved_for_ingestion", "approved_for_runtime_use") or source.get("licence_status") != "verified":
        why.append("source_not_approved_for_ingestion_with_verified_licence")
    if not file_integrity_ok:
        why.append("original_file_hash_not_verified")
    if soc_level is None:
        why.append("occupation_not_a_canonical_soc_2018_node")
    elif {"detailed": "detailed", "broad": "broad", "minor": "broad", "major": "broad"}[soc_level] != rec["occupation_level"]:
        why.append("occupation_level_disagrees_with_soc_structure")
    if rec["value_status"] != "reported" or rec["value"] is None or rec["value"] <= 0:
        why.append("no_positive_reported_value")
    if rec["measure"] == "unknown" or rec["pay_period"] not in ("annual", "hourly") or rec["pay_basis"] != "gross" or rec["currency"] != "USD":
        why.append("measurement_definition_incomplete")
    if rec["earnings_concept"] != "wage_statistic" or rec["population_scope"] != "employees" or rec["evidence_method"] != "survey":
        why.append("concept_population_or_method_unrecorded")
    if rec["geography_level"] != "national" or rec["country"] != "US" or rec["region"]:
        why.append("geography_not_national_us")
    if not rec["reference_period"] or not rec["reference_year"] or not rec["publication_date"]:
        why.append("reference_or_publication_period_missing")
    if any(k not in prov for k in _PROVENANCE_KEYS) or len(str(prov.get("archive_sha256", ""))) != 64 or not rec.get("batch_id"):
        why.append("provenance_incomplete")
    if rec["measure"] == "mean" and not isinstance(prov.get("mean_prse"), (int, float)):
        why.append("mean_without_published_rse")
    if why:
        # a failed deterministic rule is an engineering defect: the record is INSUFFICIENT for qualification (never repaired or guessed)
        return "INSUFFICIENT", why
    return "ENGINEERING_CHECKED", ["all_engineering_rules_hold", "no_precision_claim_made" if rec["measure"] != "mean" else "mean_rse_preserved_no_precision_claim"]


# ----------------------------------------------------------------------------------------------------------------------------------------------------- RSE
def _q(vals: list[float], p: float) -> float:
    vals = sorted(vals)
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (k - lo), 3)


def rse_distribution(rows: Iterable[OewsRow], canonical_codes: set[str]) -> dict[str, Any]:
    """Descriptive distribution of the PUBLISHED employment and mean-wage relative standard errors over the canonical occupations. The reported counts above 10, 25 and 50 percent are
    descriptive reference points, NOT thresholds: no cutoff exists and none is applied."""
    seen: set[str] = set()
    emp: list[float] = []
    mean: list[float] = []
    missing = Counter()
    for r in rows:
        code = str(r.values.get("OCC_CODE") or "")
        if code not in canonical_codes or code in seen:
            continue
        seen.add(code)
        for name, bucket in (("EMP_PRSE", emp), ("MEAN_PRSE", mean)):
            v = r.values.get(name)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                bucket.append(float(v))
            else:
                missing[name] += 1
    out: dict[str, Any] = {"occupations": len(seen), "missing_or_nonnumeric": dict(missing), "published_for_statistics": ["employment (EMP_PRSE)", "mean wage (MEAN_PRSE)"],
                           "not_published_for": ["median wage", "wage percentiles"],
                           "note": "BLS publishes no relative standard error for the median or the percentiles: no precision statement about them is made."}
    for name, vals in (("emp_prse", emp), ("mean_prse", mean)):
        out[name] = {"n": len(vals), "min": min(vals), "p25": _q(vals, .25), "median": _q(vals, .5), "p75": _q(vals, .75), "p90": _q(vals, .9), "p99": _q(vals, .99), "max": max(vals),
                     "descriptive_counts_above": {f"{t}%": sum(1 for v in vals if v > t) for t in (10, 25, 50)}}
    return out


# ------------------------------------------------------------------------------------------------------------------------------ annual-only reconciliation
def annual_only_reconciliation(rows: Iterable[OewsRow], soc_codes: set[str], quarantined: set[str]) -> dict[str, Any]:
    """Exact reconciliation of the source's ANNUAL=TRUE rows (the earlier acquisition report counted rows) with the canonical-occupation count of the ingestion report."""
    table = []
    for r in rows:
        if str(r.values.get("ANNUAL") or "").strip().upper() == "TRUE":
            code = str(r.values.get("OCC_CODE"))
            table.append({"source_row": r.row, "occ_code": code, "o_group": r.values.get("O_GROUP"), "in_soc_2018": code in soc_codes, "quarantined_policy_a": code in quarantined,
                          "counted_as_canonical_annual_only_occupation": code in soc_codes and code not in quarantined})
    canonical = {t["occ_code"] for t in table if t["counted_as_canonical_annual_only_occupation"]}
    return {"annual_true_rows": len(table), "by_o_group": dict(Counter(t["o_group"] for t in table)), "duplicate_presentations_among_them": len(table) - len({t["occ_code"] for t in table}),
            "canonical_annual_only_occupations": len(canonical), "excluded_rows": [t for t in table if not t["counted_as_canonical_annual_only_occupation"]], "rows": table,
            "explanation": "the earlier acquisition count (81) is source ROWS with ANNUAL=TRUE; the ingestion count (79) is canonical OCCUPATIONS; the difference is exactly the rows of the two quarantined BLS-specific aggregates listed in excluded_rows"}


# ------------------------------------------------------------------------------------------------------------------------------------- alias evidence rule
def _stem(w: str) -> str:
    w = w.lower()
    return w[:-1] if w.endswith("s") and not w.endswith("ss") else w


def title_tokens(text: str) -> list[str]:
    return [_stem(x) for x in re.findall(r"[a-z]+", text.lower())]


def soc_title_candidates(title: str, structure: list[SocNode]) -> list[SocNode]:
    """THE evidence rule: detailed SOC 2018 occupations whose OFFICIAL title contains every word of the market title (singular and plural treated as one word). It is a documented, reproducible
    containment test over an approved official source, not a similarity score: no synonyms, no popularity, no model knowledge."""
    want = title_tokens(title)
    if not want:
        return []
    return [n for n in structure if n.level == "detailed" and all(w in set(title_tokens(n.title)) for w in want)]


def build_alias_proposals(case_titles: dict[str, str], structure: list[SocNode], definitions: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """One decision per product-coverage title. ``PROPOSED_SINGLE``: exactly one official detailed title contains the market title; ``AMBIGUOUS``: several do (no alias is created, the resolver
    keeps abstaining); ``NO_AUTHORITATIVE_EVIDENCE``: none does (abstention preserved; nothing is invented). A proposal is never ``qualified`` here."""
    out = []
    for case_id, title in case_titles.items():
        cands = soc_title_candidates(title, structure)
        base = {"case": case_id, "market_title": title, "language": "en", "country_applicability": ["US"], "taxonomy": "soc", "taxonomy_edition": SOC_EDITION,
                "evidence_source": "us_soc_2018 (official 2018 SOC structure and definitions, hashes in the acquisition manifest)", "rule": "official_detailed_title_contains_all_words"}
        if len(cands) == 1:
            n = cands[0]
            exact_plural = title_tokens(title) == title_tokens(n.title)
            out.append({**base, "decision": "PROPOSED_SINGLE", "target_code": n.code, "target_label": n.title,
                        "relationship": "grammatical_number_variant_of_official_title" if exact_plural else "market_title_is_a_component_of_the_official_title",
                        "definition_excerpt": definitions.get(n.code, {}).get("definition", "")[:240],
                        "limitation": None if exact_plural else "the official title is broader than the market title; a reviewer must confirm that the occupation scope is acceptable",
                        "qualification_status_target": "engineering_checked", "approval": "PENDING_HUMAN_REVIEW (no reviewer exists in the isolated environment)"})
        elif len(cands) > 1:
            out.append({**base, "decision": "AMBIGUOUS", "candidates": [{"code": n.code, "label": n.title} for n in cands], "approval": "none: no alias is created"})
        else:
            out.append({**base, "decision": "NO_AUTHORITATIVE_EVIDENCE", "candidates": [], "approval": "none: abstention preserved",
                        "reviewer_note": "no official SOC 2018 detailed title contains this market title; an alias would need evidence from an approved source (for example a separately approved occupational-title dataset)"})
    return out
