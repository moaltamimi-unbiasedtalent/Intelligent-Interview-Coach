"""The frozen R1.0 BETA-SCOPE coverage measure, reported BESIDE the preserved historical gate (package 02E; OD-COVERAGE, BL-11, M-DOC-COVERAGE).

TWO MEASURES, NEVER MERGED
* HISTORICAL GATE: the existing 412-case product-coverage evaluation. Recorded result: 386 of 412 on the ``developer_local`` profile (258 of 412 on
  ``clean_checkout``) against the unchanged 95% threshold of 392: FAIL (BELOW_GATE). This module only READS the recorded baseline
  (``evaluations/product_coverage/baseline_gate_status.json``); it never re-runs, rewrites or reinterprets it, and the evaluator semantics
  (``scripts/eval_product_coverage.py``, ``scripts/check_product_coverage_baseline.py``) are untouched.
* BETA-SCOPE MEASURE (this module): coverage over ONLY what the closed beta actually offers:
      in scope  =  feature ENABLED  x  market APPROVED  x  at least one QUALIFIED source for that market that can answer the case
  The three sets come from the approval register (the 02D retrieval-approval and market-qualification decisions). This measure is never labelled,
  worded or computed as the original gate.

THE REGISTER TODAY IS EMPTY. 02D has approved no source and no market, so the beta scope is empty, the denominator is 0, and the measure says
``NO_APPROVED_SCOPE`` (never 0%, never 100%, never PASS). The report states this plainly. When 02D approves sources, the register file is updated by
its owner and this evaluator measures exactly that scope with no code change. The cases were NOT chosen to fit a scope: the frozen case set is a
fixed grid of feature x market candidates (see :func:`generate_candidate_cases`), the scope filter selects from it.

NO THRESHOLD IS INVENTED. OD-COVERAGE has not set a beta-scope pass threshold, so the measure reports counts and a percentage only; its verdict is
``NO_APPROVED_SCOPE``, ``NOT_EVALUATED`` (scope exists but no sufficiency outcomes were supplied) or ``REPORTED_NO_THRESHOLD``.

FROZEN DATASET: ``evaluations/beta_scope_coverage/cases_v1.json``, hash recorded in :data:`FROZEN_CASES_SHA256`; a changed file is refused and a test
asserts the committed file equals :func:`generate_candidate_cases` (reproducible). INDEPENDENCE LIMITATION: the grid, occupations, queries and
expected source families were authored by engineering, not an independent reviewer; they are English-only (language is a separate dimension).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

__all__ = ["MEASURE_ID", "FROZEN_CASES_SHA256", "CASES_PATH", "REGISTER_PATH", "HISTORICAL_BASELINE_PATH", "HISTORICAL_TOTAL", "HISTORICAL_GATE_PERCENT",
           "ApprovalRegister", "BetaCase", "CoverageDatasetError", "load_register", "load_cases", "generate_candidate_cases", "historical_measure",
           "beta_scope_measure", "report_both", "REPORTING_RULE"]

ROOT = Path(__file__).resolve().parents[3]
CASES_PATH = ROOT / "evaluations" / "beta_scope_coverage" / "cases_v1.json"
REGISTER_PATH = ROOT / "evaluations" / "beta_scope_coverage" / "approval_register.json"
HISTORICAL_BASELINE_PATH = ROOT / "evaluations" / "product_coverage" / "baseline_gate_status.json"
MEASURE_ID = "beta-scope-coverage/1"
FROZEN_CASES_SHA256 = "dff623f5b2b8cbb6624886441f47825c56724f5ac39bd80135101241108bcb1e"
HISTORICAL_TOTAL, HISTORICAL_GATE_PERCENT = 412, 95
REPORTING_RULE = ("Both measures are always reported together. The historical gate (412 cases, 95% = 392) is preserved unchanged and is not "
                  "replaced, relaxed or re-labelled by the beta-scope measure; the beta-scope measure is never called the original gate.")

# Candidate grid: the lanes a candidate can reach through knowledge retrieval x the markets the product names. Source families are the source ids that can
# answer the feature in that market (from ``constants.COUNTRY_SOURCE_PRIORITY`` and the governed datasets); a market with no national source lists the
# EU/international family, never another country's statistics.
FEATURES = {
    "role_definition": ("What does a {occ} do in {place}?", "structured_role"),
    "compensation": ("What does a {occ} earn in {place}?", "compensation"),
    "labour_outlook": ("How is demand for {occ} roles expected to develop in {place}?", "forecast"),
    "entry_education": ("What education is needed to become a {occ} in {place}?", "education"),
    "licence": ("Is a licence required to work as a {occ} in {place}?", "licence"),
    "certification": ("Which professional certifications help a {occ} in {place}?", "certification"),
}
MARKETS = {  # code -> (place name used in the question, source family)
    "DE": ("Germany", ("kldb", "berufenet", "ba_kompetenzkatalog", "ba_entgeltatlas")),
    "UK": ("the United Kingdom", ("ons_ashe", "uk_civil_service_success_profiles", "uk_hr_success_profiles")),
    "US": ("the United States", ("onet", "bls_ooh", "bls_oews")),
    "FR": ("France", ("esco", "eurostat_earnings")),
    "ES": ("Spain", ("esco", "eurostat_earnings")),
    "IT": ("Italy", ("esco", "eurostat_earnings")),
    "PT": ("Portugal", ("esco", "eurostat_earnings")),
    "NL": ("the Netherlands", ("esco", "eurostat_earnings")),
    "EU": ("the European Union", ("esco", "esco_matrix", "eurostat_earnings", "cedefop_skills_forecast")),
}
OCCUPATIONS = ("Data Analyst", "Accountant")


class CoverageDatasetError(Exception):
    """The case set or the register is missing, malformed or does not match its recorded hash. Fail closed: no measure is reported from it."""


@dataclass(frozen=True)
class BetaCase:
    case_id: str
    feature: str
    market: str
    occupation: str
    query: str
    expected_lane: str
    source_family: tuple[str, ...]


@dataclass(frozen=True)
class ApprovalRegister:
    """The beta scope as decided by 02D / OD-COVERAGE. ``qualified_sources`` are ``(source_id, market)`` pairs. All three sets empty = nothing approved."""

    enabled_features: frozenset[str]
    approved_markets: frozenset[str]
    qualified_sources: frozenset[tuple[str, str]]
    sha256: str
    problems: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.enabled_features and self.approved_markets and self.qualified_sources)


def generate_candidate_cases() -> list[dict]:
    """The deterministic candidate grid (feature x market x occupation), sorted by id. The committed file is exactly this output."""
    out = []
    for feature, (tmpl, lane) in FEATURES.items():
        for market, (place, family) in MARKETS.items():
            for i, occ in enumerate(OCCUPATIONS, start=1):
                out.append({"id": f"bs_{feature}_{market.lower()}_{i}", "feature": feature, "market": market, "occupation": occ,
                            "query": tmpl.format(occ=occ, place=place), "expected_lane": lane, "source_family": list(family)})
    return sorted(out, key=lambda c: c["id"])


def _canonical(cases: list[dict]) -> bytes:
    doc = {"name": "beta_scope_coverage_cases_v1", "schema_version": 1, "frozen": True,
           "independence": "authored by engineering; no independent reviewer; English-only questions",
           "description": "Candidate grid of feature x market x occupation questions. A case is IN SCOPE only when its feature is enabled, its market approved and one of "
                          "its source-family sources qualified for that market in the approval register. Selection never edits this file.",
           "count": len(cases), "cases": cases}
    return (json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_cases(path: Path | None = None, *, expected_sha256: str | None = None) -> tuple[list[BetaCase], str]:
    p = path or CASES_PATH
    expected = FROZEN_CASES_SHA256 if expected_sha256 is None and path is None else expected_sha256
    try:
        raw = p.read_bytes()
    except OSError:
        raise CoverageDatasetError("the beta-scope case set is missing") from None
    digest = _sha(raw)
    if expected is not None and digest != expected:
        raise CoverageDatasetError("the beta-scope case set does not match its recorded hash (it is frozen)")
    try:
        data = json.loads(raw.decode("utf-8"))
        cases = [BetaCase(c["id"], c["feature"], c["market"], c["occupation"], c["query"], c["expected_lane"], tuple(c["source_family"])) for c in data["cases"]]
    except Exception:  # noqa: BLE001
        raise CoverageDatasetError("the beta-scope case set is malformed") from None
    if len({c.case_id for c in cases}) != len(cases):
        raise CoverageDatasetError("the beta-scope case set has duplicate ids")
    return cases, digest


def load_register(path: Path | None = None) -> ApprovalRegister:
    """Read the approval register. A missing, unreadable or malformed register is reported as EMPTY with a problem code: unknown approval is never assumed."""
    p = path or REGISTER_PATH
    try:
        raw = p.read_bytes()
    except OSError:
        return ApprovalRegister(frozenset(), frozenset(), frozenset(), _sha(b""), ("register_missing",))
    digest = _sha(raw)
    try:
        d = json.loads(raw.decode("utf-8"))
        feats = frozenset(str(x) for x in d["enabled_features"])
        markets = frozenset(str(x) for x in d["approved_markets"])
        sources = frozenset((str(s["source_id"]), str(s["market"])) for s in d["qualified_sources"])
    except Exception:  # noqa: BLE001
        return ApprovalRegister(frozenset(), frozenset(), frozenset(), digest, ("register_malformed",))
    problems = []
    if feats - set(FEATURES):
        problems.append("unknown_feature_in_register")
    if markets - set(MARKETS):
        problems.append("unknown_market_in_register")
    if any(m not in markets for _, m in sources):
        problems.append("qualified_source_for_unapproved_market")    # a source cannot qualify a market that is not approved
    if problems:
        return ApprovalRegister(frozenset(), frozenset(), frozenset(), digest, tuple(problems))
    return ApprovalRegister(feats, markets, sources, digest)


def _in_scope(c: BetaCase, reg: ApprovalRegister) -> bool:
    return (c.feature in reg.enabled_features and c.market in reg.approved_markets
            and any((s, c.market) in reg.qualified_sources for s in c.source_family))


def historical_measure(path: Path | None = None) -> dict:
    """The preserved historical gate, READ from its recorded baseline. Never recomputed from a run, never modified."""
    p = path or HISTORICAL_BASELINE_PATH
    try:
        raw = p.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        profiles = data["profiles"]
    except Exception:  # noqa: BLE001
        raise CoverageDatasetError("the historical coverage baseline is missing or malformed") from None
    required = math.ceil(HISTORICAL_TOTAL * HISTORICAL_GATE_PERCENT / 100)        # 392 of 412
    out: dict[str, Any] = {}
    for name in sorted(profiles):
        prof = profiles[name]
        suff, total = int(prof["sufficient"]), int(prof["cases"])
        out[name] = {"sufficient": suff, "cases": total, "required_for_gate": required, "percent": round(100.0 * suff / total, 2) if total else None,
                     "verdict": "FAIL" if (total != HISTORICAL_TOTAL or suff < required) else "AT_OR_ABOVE_GATE_REPORTED",
                     "recorded_on": prof.get("recorded_on")}
    return {"measure": "historical product-coverage gate (preserved unchanged)", "threshold_percent": HISTORICAL_GATE_PERCENT, "profiles": out,
            "source": "evaluations/product_coverage/baseline_gate_status.json", "source_sha256": _sha(raw), "unchanged": True,
            "note": "Read from the recorded baseline. The owner accepted the BELOW_GATE baseline for the Capstone engineering scope as a limitation, not a pass."}


def beta_scope_measure(register: ApprovalRegister, cases: list[BetaCase], cases_sha256: str, sufficiency: Mapping[str, bool] | None = None) -> dict:
    """Coverage over the approved beta scope. ``sufficiency`` maps case id -> sufficient (supplied by a governed evaluation run; none is produced here)."""
    scope = [c for c in cases if _in_scope(c, register)]
    by_feature: dict[str, int] = {}
    for c in scope:
        by_feature[c.feature] = by_feature.get(c.feature, 0) + 1
    base: dict[str, Any] = {"measure": "R1.0 beta-scope coverage (NOT the historical gate)", "measure_id": MEASURE_ID,
                            "definition": "enabled features x approved markets x qualified sources only, from the 02D approval register",
                            "dataset": {"path": "evaluations/beta_scope_coverage/cases_v1.json", "sha256": cases_sha256, "candidate_cases": len(cases)},
                            "register": {"sha256": register.sha256, "enabled_features": sorted(register.enabled_features),
                                         "approved_markets": sorted(register.approved_markets),
                                         "qualified_sources": sorted(f"{s}@{m}" for s, m in register.qualified_sources), "problems": list(register.problems)},
                            "threshold": None, "threshold_note": "OD-COVERAGE has not set a beta-scope threshold; none is assumed.",
                            "in_scope_cases": len(scope), "in_scope_by_feature": dict(sorted(by_feature.items())),
                            "independence_limitation": "case set authored by engineering, English-only; not independently reviewed"}
    if not scope:
        return {**base, "verdict": "NO_APPROVED_SCOPE", "sufficient": None, "denominator": 0, "percent": None,
                "statement": "No feature, market and qualified source combination is approved yet (02D has approved no source), so the beta scope is empty and "
                             "nothing can be measured. This is not 0% and not 100%, and it is not a pass."}
    if sufficiency is None or any(c.case_id not in sufficiency for c in scope):
        return {**base, "verdict": "NOT_EVALUATED", "sufficient": None, "denominator": len(scope), "percent": None,
                "statement": "A beta scope exists but sufficiency outcomes were not supplied for every in-scope case; no coverage figure is reported."}
    ok = sum(1 for c in scope if sufficiency[c.case_id])
    return {**base, "verdict": "REPORTED_NO_THRESHOLD", "sufficient": ok, "denominator": len(scope), "percent": round(100.0 * ok / len(scope), 2),
            "statement": f"{ok} of {len(scope)} in-scope cases sufficient. No threshold is defined, so this is a report, not a pass or a fail."}


def report_both(*, register: ApprovalRegister | None = None, cases_path: Path | None = None, baseline_path: Path | None = None,
                sufficiency: Mapping[str, bool] | None = None) -> dict:
    """The ONLY reporting entry point: always returns BOTH measures side by side. A caller cannot obtain one without the other."""
    cases, digest = load_cases(cases_path, expected_sha256=None if cases_path is not None else FROZEN_CASES_SHA256)
    reg = register or load_register()
    return {"schema_version": 1, "reporting_rule": REPORTING_RULE, "historical_gate": historical_measure(baseline_path),
            "beta_scope": beta_scope_measure(reg, cases, digest, sufficiency), "pg_05_claimed": False,
            "note": "PG-05 is NOT claimed met by this report."}
