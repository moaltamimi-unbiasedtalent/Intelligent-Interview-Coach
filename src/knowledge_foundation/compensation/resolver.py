"""Internal compensation resolution service (GKB-5). NON-OPERATIONAL and imported by no candidate-facing path. It never returns a number it cannot trace, never guesses an occupation,
never falls back to another country, never combines incompatible measurements and abstains (C4) when qualifying evidence is absent.

Order of work: explicit country (never from a language) -> comparison mode -> occupation identity via the P10C-B resolver (AMBIGUOUS, INSUFFICIENT_CONTEXT, UNSUPPORTED and NOT_FOUND are
passed through, never replaced by a salary) -> evidence for the occupation (exact first; a verified broader-group relationship only as a clearly labelled lower-specificity fallback)
-> eligibility (runtime-approved and qualified by default, presentable class, traceable citation) -> recency -> comparability groups -> precedence inside a comparable group ->
conflict preservation. Precedence only orders evidence that already matches the request; it cannot override missing or incompatible evidence.

``require_operational`` defaults to True: until a source is approved for runtime use and a measurement is qualified, evidence is WITHHELD (the response says so) and the outcome is a
C4 abstention. Internal evaluation passes ``require_operational=False`` to exercise the logic on synthetic fixtures; such a response is flagged non-presentable."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from src.knowledge_foundation.compensation.confidence import assess_evidence_state
from src.knowledge_foundation.compensation.countries import normalize_region, profile_for
from src.knowledge_foundation.compensation.policy import PrecedencePolicy, normalize_country
from src.knowledge_foundation.compensation.store import CompensationStoreV2, build_citation, evidence_status
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver, ResolutionOutcome
from src.knowledge_foundation.qualification import qualify_relationship
from src.knowledge_foundation.registry import SourceRegistry

__all__ = ["CompensationOutcome", "CompensationRequest", "CompensationResponse", "CompensationResolver", "FxProvider", "PppProvider"]

COMPARISON_MODES = ("nominal", "fx_converted", "ppp_adjusted")


class CompensationOutcome(str, Enum):
    EVIDENCE = "evidence"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    UNSUPPORTED = "unsupported"
    NOT_FOUND = "not_found"
    ABSTAIN = "abstain"                  # C4: insufficient evidence
    CONFLICT = "conflict"                # comparable-looking evidence that disagrees, or incompatible measurements, preserved and not combined
    NOT_CONFIGURED = "not_configured"    # FX or PPP comparison: no approved source or methodology exists


class FxProvider:
    """Interface only (no implementation, no source, no rate). An FX-converted comparison needs an approved source and methodology (PENDING OWNER APPROVAL)."""

    def rate(self, base: str, quote: str, as_of_year: int):  # pragma: no cover - interface
        raise NotImplementedError


class PppProvider:
    """Interface only. A purchasing-power comparison needs an approved source and methodology (PENDING OWNER APPROVAL)."""

    def factor(self, country: str, as_of_year: int):  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class CompensationRequest:
    occupation: MultilingualRequest = field(default_factory=MultilingualRequest)
    country: str | None = None                       # explicit employment country; never inferred from a language
    region: str | None = None
    reference_year: int | None = None
    pay_period: str | None = None
    measure: str | None = None
    percentile: int = 0
    earnings_concept: str | None = None              # optional filters on what the figure measures, who it covers and how it was produced
    population_scope: str | None = None
    evidence_method: str | None = None
    comparison_mode: str = "nominal"
    allow_broader_occupation: bool = True
    require_operational: bool = True


@dataclass
class CompensationResponse:
    outcome: CompensationOutcome
    country: str | None = None
    occupation_status: str | None = None
    occupation_key: str | None = None
    matched_occupation_key: str | None = None
    occupation_specificity: str | None = None        # exact | broader_group
    candidates: list[dict[str, Any]] = field(default_factory=list)
    context_needed: list[str] = field(default_factory=list)
    evidence_class: str | None = None                # C1 | C2 | C3 | C4
    value: str | None = None
    lower_value: str | None = None
    upper_value: str | None = None
    bounds_semantic: str | None = None
    currency: str | None = None
    pay_period: str | None = None
    pay_basis: str | None = None
    measure: str | None = None
    percentile: int = 0
    earnings_concept: str | None = None
    population_scope: str | None = None
    evidence_method: str | None = None
    geography_level: str | None = None
    region: str | None = None
    reference_year: int | None = None
    data_vintage: str | None = None
    citation: dict[str, Any] | None = None
    coverage_limitations: list[str] = field(default_factory=list)
    abstention_reason: str | None = None
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    corroborating: list[dict[str, Any]] = field(default_factory=list)
    withheld: dict[str, int] = field(default_factory=dict)
    precedence_category: str | None = None
    occupation_level: str | None = None
    precedence_pending: bool = False
    freshness: dict[str, Any] | None = None
    fallback_trace: dict[str, Any] | None = None
    fallback: dict[str, Any] | None = None
    evidence_assessment: dict[str, Any] | None = None
    comparison_mode: str = "nominal"
    comparison_mode_status: str = "supported"
    policy_version: str | None = None
    operational: bool = False
    candidate_presentable: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        """The internal response contract. Carries no registry secret, licence detail or private import metadata; amounts are exact decimal strings."""
        d = {k: v for k, v in self.__dict__.items()}
        d["outcome"] = self.outcome.value
        return d


class _Sources:
    """Per-resolution memo of registry reads (the registry is queried once per distinct source)."""

    def __init__(self, registry: SourceRegistry) -> None:
        self._r, self._get, self._ev = registry, {}, {}

    def get(self, sid: str):
        if sid not in self._get:
            self._get[sid] = self._r.get(sid)
        return self._get[sid]

    def can_serve_as_evidence(self, sid: str) -> bool:
        if sid not in self._ev:
            self._ev[sid] = self._r.can_serve_as_evidence(sid)
        return self._ev[sid]


def _summary(rec: dict[str, Any]) -> dict[str, Any]:
    return {"source_id": rec["source_ref"], "source_edition": rec["source_edition"], "native_code": rec["native_code"], "value": str(rec["value"]) if rec["value"] is not None else None,
            "currency": rec["currency"], "pay_period": rec["pay_period"], "pay_basis": rec["pay_basis"], "measure": rec["measure"], "reference_year": rec["reference_year"],
            "evidence_class": rec["evidence_class"], "precedence_category": rec["precedence_category"], "earnings_concept": rec["earnings_concept"],
            "population_scope": rec["population_scope"], "evidence_method": rec["evidence_method"], "region": rec["region"]}


class CompensationResolver:
    def __init__(self, store: CompensationStoreV2, occupation_resolver: OccupationResolver, graph: OccupationGraph, registry: SourceRegistry, *, coverage=None,
                 policy: PrecedencePolicy | None = None) -> None:
        self._store, self._occ, self._g, self._reg, self._cov = store, occupation_resolver, graph, registry, coverage
        self.policy = policy or store.policy

    # ----------------------------------------------------------------------------------------------------------------------------------- entry
    def resolve(self, req: CompensationRequest) -> CompensationResponse:
        resp = CompensationResponse(CompensationOutcome.INSUFFICIENT_CONTEXT, policy_version=self.policy.version, comparison_mode=req.comparison_mode)
        if req.comparison_mode not in COMPARISON_MODES:
            return self._finish(resp, CompensationOutcome.INSUFFICIENT_CONTEXT, reason="unknown_comparison_mode", context=["comparison_mode"])
        if req.comparison_mode != "nominal":
            resp.comparison_mode_status = "not_configured"
            return self._finish(resp, CompensationOutcome.NOT_CONFIGURED, reason=f"{req.comparison_mode}_not_configured_no_approved_source_or_methodology")
        country = normalize_country(req.country)
        resp.country = country
        if country is None:
            return self._finish(resp, CompensationOutcome.INSUFFICIENT_CONTEXT, reason="country_required", context=["country"])
        if self._cov is not None:
            row = self._cov.get(country)
            if row is None or row["compensation_level"] == "unsupported":
                return self._finish(resp, CompensationOutcome.UNSUPPORTED, reason="country_not_supported")
        if req.region and profile_for(country) is not None:
            norm = normalize_region(country, req.region)
            if norm is None:
                return self._finish(resp, CompensationOutcome.INSUFFICIENT_CONTEXT, reason="region_unrecognised", context=["region"])
            req = replace(req, region=norm)
        occ = self._occ.resolve(replace(req.occupation, country=country))
        resp.occupation_status = occ.outcome.value
        resp.candidates = [{"occupation_key": c.occupation_key, "canonical_label": c.canonical_label, "grade": c.grade} for c in occ.candidates]
        resp.context_needed = list(occ.context_needed)
        if occ.outcome is not ResolutionOutcome.RESOLVED:
            mapped = {ResolutionOutcome.AMBIGUOUS: CompensationOutcome.AMBIGUOUS, ResolutionOutcome.INSUFFICIENT_CONTEXT: CompensationOutcome.INSUFFICIENT_CONTEXT,
                      ResolutionOutcome.UNSUPPORTED: CompensationOutcome.UNSUPPORTED, ResolutionOutcome.NOT_FOUND: CompensationOutcome.NOT_FOUND}[occ.outcome]
            return self._finish(resp, mapped, reason=occ.reasons[0] if occ.reasons else occ.outcome.value, context=resp.context_needed)
        resp.occupation_key = occ.candidates[0].occupation_key
        return self._evidence(req, resp, country)

    # ------------------------------------------------------------------------------------------------------------------------------ evidence
    def _evidence_nodes(self, key: str, req: CompensationRequest) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
        """(exact node keys, broader node keys). Exact = the node itself plus VERIFIED equivalents; broader = VERIFIED ``broader`` targets (one hop). RELATED, NARROWER, unverified and
        derived-rule relationships never carry evidence. In operational mode a relationship must also be official-source-provided."""
        exact, broader, info = [key], [], {}
        rels = self._g.relationships(key) + self._g.relationships(key, direction="in")
        for r in rels:
            if r["mapping_status"] != "verified" or r["superseded"]:
                continue
            if req.require_operational and not qualify_relationship(r, self._reg)["official_source_provided"]:
                continue
            other = r["to_key"] if r["from_key"] == key else r["from_key"]
            q = qualify_relationship(r, self._reg)["highest_level"]
            if r["relationship_type"] == "equivalent" and other not in exact:
                exact.append(other)
                info[other] = {"relationship_type": "equivalent", "mapping_status": r["mapping_status"], "qualification": q}
            elif r["relationship_type"] == "broader" and r["from_key"] == key and other not in broader:
                broader.append(other)
                info[other] = {"relationship_type": "broader", "mapping_status": r["mapping_status"], "qualification": q}
        return exact, broader, info

    def _ids(self, keys: list[str]) -> dict[int, str]:
        from sqlalchemy import select
        from src.persistence import GraphOccupation
        if not keys:
            return {}
        with self._g._sf() as s:
            return {i: k for i, k in s.execute(select(GraphOccupation.id, GraphOccupation.occupation_key).where(GraphOccupation.occupation_key.in_(keys))).all()}

    def _eligible(self, recs: list[dict[str, Any]], req: CompensationRequest, src: _Sources, withheld: dict[str, int]) -> list[dict[str, Any]]:
        out = []
        region = (req.region or "").strip().lower()
        for r in recs:
            if (r["region"] or "").lower() != region:
                continue
            if req.pay_period and r["pay_period"] != req.pay_period:
                continue
            if r["earnings_concept"] == "household_income":
                withheld["household_income_is_not_occupation_compensation"] = withheld.get("household_income_is_not_occupation_compensation", 0) + 1
                continue
            if (req.earnings_concept and r["earnings_concept"] != req.earnings_concept) or (req.population_scope and r["population_scope"] != req.population_scope) \
                    or (req.evidence_method and r["evidence_method"] != req.evidence_method):
                continue
            if req.measure and (r["measure"] != req.measure or (req.measure == "percentile" and r["percentile"] != req.percentile)):
                continue
            if r["measure"] == "unknown":
                withheld["measure_unknown"] = withheld.get("measure_unknown", 0) + 1       # an unknown statistic is never presented or compared
                continue
            if r["value_status"] != "reported":
                withheld["source_value_suppressed"] = withheld.get("source_value_suppressed", 0) + 1
                continue
            if not self.policy.presentable(r["precedence_category"], r["evidence_class"]):
                withheld["class_not_presentable_under_policy"] = withheld.get("class_not_presentable_under_policy", 0) + 1
                continue
            if self.policy.precedence_pending(src.get(r["source_ref"])) and req.require_operational:
                withheld["precedence_decision_pending"] = withheld.get("precedence_decision_pending", 0) + 1       # no operational result may rest on an unapproved precedence choice (D-16)
                continue
            if build_citation(r, src) is None:                                       # type: ignore[arg-type]
                withheld["citation_incomplete"] = withheld.get("citation_incomplete", 0) + 1
                continue
            if req.require_operational and not evidence_status(r, src, self.policy)["operational"]:   # type: ignore[arg-type]
                withheld["not_operational"] = withheld.get("not_operational", 0) + 1
                continue
            out.append(r)
        return out

    @staticmethod
    def _group_key(r: dict[str, Any]) -> tuple:
        measure = (r["measure"], r["percentile"]) if r["measure"] != "unknown" else None
        basis = r["pay_basis"] if r["pay_basis"] != "unknown" else None
        key = (r["country"], r["region"] or "", r["geography_level"], r["currency"], r["pay_period"], basis, measure, r["reference_year"], r["earnings_concept"], r["population_scope"], r["evidence_method"])
        return key + ((r["source_ref"], r["source_edition"], r["id"]),) if (basis is None or measure is None) else key       # an unknown basis or measure is comparable with nothing

    def _evidence(self, req: CompensationRequest, resp: CompensationResponse, country: str) -> CompensationResponse:
        src = _Sources(self._reg)
        withheld: dict[str, int] = {}
        exact_keys, broader_keys, rel_info = self._evidence_nodes(resp.occupation_key, req)
        ids = self._ids(exact_keys + broader_keys)
        by_key = {k: i for i, k in ids.items()}
        chosen: list[dict[str, Any]] = []
        specificity = "exact"
        recs = self._store.records_for([by_key[k] for k in exact_keys if k in by_key], country)
        chosen = self._eligible(recs, req, src, withheld)
        if not chosen and req.allow_broader_occupation and broader_keys:
            recs = self._store.records_for([by_key[k] for k in broader_keys if k in by_key], country)
            chosen = self._eligible(recs, req, src, withheld)
            specificity = "broader_group"
        resp.fallback_trace = {"order": ["exact_occupation", "verified_broader_group"], "selected_stage": {"exact": "exact_occupation", "broader_group": "verified_broader_group"}[specificity] if chosen else None, "broader_group_attempted": bool(broader_keys) and req.allow_broader_occupation,
                               "eligible_records_by_class_at_selected_stage": {c: sum(1 for r in chosen if r["evidence_class"] == c) for c in ("C1", "C2", "C3")}, "other_country_evidence_used": False}
        resp.withheld = withheld
        if not chosen:
            reason = ("evidence_exists_but_is_not_operational" if withheld.get("not_operational") else "evidence_withheld_precedence_decision_pending" if withheld.get("precedence_decision_pending")
                      else "source_value_suppressed" if withheld.get("source_value_suppressed")
                      else "evidence_withheld_citation_incomplete" if withheld.get("citation_incomplete")
                      else "no_evidence_for_requested_region" if req.region else "no_evidence_for_occupation_in_country")
            resp.evidence_class = "C4"
            resp.abstention_reason = reason
            if self._cov is not None:
                row = self._cov.get(country)
                if row is not None:
                    resp.coverage_limitations.append(f"country coverage for compensation: {row['compensation_level']}")
            return self._finish(resp, CompensationOutcome.ABSTAIN, reason=reason)
        all_years = {r["reference_year"] for r in chosen}                                 # reference years among ELIGIBLE evidence (before any year filter)
        if req.reference_year is not None:
            chosen = [r for r in chosen if r["reference_year"] == req.reference_year]
            if not chosen:
                resp.evidence_class, resp.abstention_reason = "C4", "no_evidence_for_requested_reference_year"
                return self._finish(resp, CompensationOutcome.ABSTAIN, reason="no_evidence_for_requested_reference_year")
        else:
            latest = max(r["reference_year"] for r in chosen)                           # policy recency: newest reference year among ELIGIBLE evidence
            chosen = [r for r in chosen if r["reference_year"] == latest]
        latest_available = chosen[0]["reference_year"] == max(all_years)
        groups: dict[tuple, list[dict[str, Any]]] = {}
        for r in chosen:
            groups.setdefault(self._group_key(r), []).append(r)
        if len(groups) > 1:
            resp.conflicts = [{"comparable": False, "best": _summary(self._best(g)[0]), "records": len(g)} for g in groups.values()]
            resp.coverage_limitations.append("the available measurements differ in currency, pay period, pay basis, statistic, region or reference year and are NOT combined")
            return self._finish(resp, CompensationOutcome.CONFLICT, reason="incompatible_measurements_preserved")
        group = next(iter(groups.values()))
        best, rest, tie = self._best(group)
        if tie:
            resp.conflicts = [{"comparable": True, "same_precedence_tier": True, "best": _summary(r)} for r in tie]
            return self._finish(resp, CompensationOutcome.CONFLICT, reason="comparable_sources_of_equal_precedence_disagree")
        resp.corroborating = [{**_summary(r), "agrees": r["value"] == best["value"]} for r in rest]
        return self._present(resp, best, specificity, by_key, ids, src, req, rel_info, latest_available)

    def _best(self, group: list[dict[str, Any]]):
        """Highest-precedence record of a comparable group. Inside that tier only the newest vintage of each (occupation, source, edition) counts; if the remaining records carry different
        values (several sources, or several candidate occupations reached through a relationship) the result is a TIE that the caller reports as a conflict. Returns (best, rest, tie)."""
        def rank(r):
            return self.policy.rank(r["precedence_category"]) or 99
        top = min(rank(r) for r in group)
        tier = sorted([r for r in group if rank(r) == top], key=lambda r: (r["data_vintage"] or "", r["publication_date"].isoformat() if r["publication_date"] else "", r["id"]), reverse=True)
        latest: dict[tuple, dict[str, Any]] = {}
        for r in tier:
            latest.setdefault((r["occupation_id"], r["source_ref"], r["source_edition"]), r)
        distinct = {(r["value"], r["lower_value"], r["upper_value"]) for r in latest.values()}
        tie = list(latest.values()) if len(distinct) > 1 else []
        return tier[0], [r for r in group if r is not tier[0]], tie

    def _present(self, resp: CompensationResponse, rec: dict[str, Any], specificity: str, by_key: dict[str, int], ids: dict[int, str], src: _Sources, req: CompensationRequest,
                 rel_info: dict[str, dict[str, Any]] | None = None, latest_available: bool | None = None):
        status = evidence_status(rec, src, self.policy)                                  # type: ignore[arg-type]
        resp.value = str(rec["value"])
        resp.lower_value = str(rec["lower_value"]) if rec["lower_value"] is not None else None
        resp.upper_value = str(rec["upper_value"]) if rec["upper_value"] is not None else None
        resp.bounds_semantic = rec["bounds_semantic"] if rec["lower_value"] is not None else None
        resp.currency, resp.pay_period, resp.pay_basis, resp.measure, resp.percentile = rec["currency"], rec["pay_period"], rec["pay_basis"], rec["measure"], rec["percentile"]
        resp.earnings_concept, resp.population_scope, resp.evidence_method = rec["earnings_concept"], rec["population_scope"], rec["evidence_method"]
        resp.geography_level, resp.region = rec["geography_level"], rec["region"]
        resp.reference_year, resp.data_vintage = rec["reference_year"], rec["data_vintage"] or None
        resp.citation = build_citation(rec, src)                                          # type: ignore[arg-type]
        resp.evidence_class = rec["evidence_class"]
        resp.occupation_specificity = specificity
        resp.matched_occupation_key = ids.get(rec["occupation_id"])
        lim = resp.coverage_limitations
        if specificity == "broader_group":
            lim.append("evidence is for a BROADER occupational group reached through a verified relationship, not for the requested occupation")
        if rec["evidence_class"] == "C2" or rec["occupation_level"] == "broad":
            lim.append("national evidence for a BROAD occupational group, not occupation-specific")
        if rec["evidence_class"] == "C3":
            lim.append("international harmonised evidence, not a national occupation-specific figure")
        if rec["geography_level"] == "regional":
            lim.append(f"REGIONAL evidence ({rec['region']}), not a national figure")
        if rec["earnings_concept"] == "unknown":
            lim.append("what the figure measures (earnings concept) is not recorded")
        if rec["pay_basis"] == "unknown":
            lim.append("the gross/net pay basis is not recorded by the source adapter")
        if rec["data_vintage"]:
            lim.append(f"data vintage: {rec['data_vintage']}")
        if rec["limitations"]:
            lim.append(rec["limitations"])
        resp.precedence_category, resp.occupation_level = rec["precedence_category"], rec["occupation_level"]
        resp.precedence_pending = self.policy.precedence_pending(src.get(rec["source_ref"]))
        if resp.precedence_pending:
            lim.append("the precedence category of this international source is PENDING owner decision D-16; the figure is never operational")
        if specificity == "broader_group" and rel_info:
            resp.fallback = dict(rel_info.get(resp.matched_occupation_key) or {})
        source = src.get(rec["source_ref"]) or {}
        retrieved = source.get("retrieved_at")
        resp.freshness = {"reference_year": rec["reference_year"], "reference_period": rec["reference_period"], "publication_date": rec["publication_date"].isoformat() if rec["publication_date"] else None,
                          "data_vintage": rec["data_vintage"] or None, "source_edition": rec["source_edition"], "source_retrieved_at": retrieved.isoformat() if retrieved else None,
                          "describes_current_market_pay": False}
        resp.outcome = CompensationOutcome.EVIDENCE
        resp.evidence_assessment = assess_evidence_state(resp, record_level=rec["occupation_level"], latest_available=latest_available)
        resp.operational = status["operational"]
        resp.candidate_presentable = bool(status["operational"] and req.require_operational)
        return self._finish(resp, CompensationOutcome.EVIDENCE, reason="evidence_selected")

    # --------------------------------------------------------------------------------------------------------------------------------- result
    @staticmethod
    def _finish(resp: CompensationResponse, outcome: CompensationOutcome, *, reason: str | None = None, context: list[str] | None = None) -> CompensationResponse:
        resp.outcome = outcome
        if reason and outcome is not CompensationOutcome.EVIDENCE and not resp.abstention_reason:
            resp.abstention_reason = reason
        if context:
            resp.context_needed = list(dict.fromkeys([*resp.context_needed, *context]))
        if outcome is not CompensationOutcome.EVIDENCE:
            resp.value = None
            resp.candidate_presentable = False
        if resp.evidence_assessment is None:
            resp.evidence_assessment = assess_evidence_state(resp)
        return resp
