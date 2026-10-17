"""Governed Compensation V2 store and importer (GKB-5). One authority for source approval: the P10C-A source registry. The importer is deterministic, edition-aware, idempotent,
schema-validated, provenance-preserving, non-destructive and transaction-safe:

* ``production`` mode needs ``SourceRegistry.can_ingest`` (approved for ingestion, VERIFIED licence, non-fixture origin), a known dataset edition, and publisher and dataset attribution;
* ``fixture`` mode needs a registered SYNTHETIC-FIXTURE source and stores rows that can never be evidence;
* a row is REJECTED (reason code only, no source content) for: schema or currency or unit problems, a source mismatch, an unknown taxonomy edition (production), an occupation that is not in
  the graph or is ambiguous, an undeterminable evidence class, or a conflicting value for an existing measurement. Nothing is repaired or invented, and nothing is ever overwritten;
* the batch is one transaction, an identical re-import is a no-op, and an audit batch records counts and reason codes only.
No candidate-facing path imports this module."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.knowledge_foundation import enums as E
from src.knowledge_foundation.compensation.policy import PrecedencePolicy, classify_evidence
from src.knowledge_foundation.compensation.record import CompensationRecordV2, from_row, record_key_for, row_values
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.registry import SourceRegistry
from src.persistence import CompensationImportBatch, CompensationRecordV2Row, OccupationTaxonomy

__all__ = ["CompensationSourceNotApproved", "ImportReport", "CompensationStoreV2", "build_citation", "evidence_status"]

_UNKNOWN_EDITIONS = ("unknown", "current release", "")


class CompensationSourceNotApproved(PermissionError):
    """The source registry does not permit this import. Carries no source content."""


@dataclass
class ImportReport:
    batch_key: str = ""
    mode: str = ""
    source_ref: str = ""
    source_edition: str = ""
    rows: int = 0
    added: int = 0
    existing: int = 0
    rejected: int = 0
    rejections: dict[str, int] = field(default_factory=dict)
    already_imported: bool = False


def build_citation(record: Mapping[str, Any], registry: SourceRegistry) -> dict[str, Any] | None:
    """A citation built ONLY from the stored measurement and the registered source it names. Returns None when it cannot be traced (unregistered source, missing publisher, dataset or
    edition, or a registry publisher that no longer matches the stored one): a measurement without a traceable citation is never presented."""
    src = registry.get(record["source_ref"]) if record.get("source_ref") else None
    if src is None or not record.get("publisher") or not record.get("dataset_name") or not record.get("source_edition") or not record.get("reference_year"):
        return None
    if src.get("publisher") and src["publisher"] != record["publisher"]:
        return None
    return {"source_id": record["source_ref"], "publisher": record["publisher"], "dataset": record["dataset_name"], "edition": record["source_edition"], "url": record.get("source_url"),
            "native_code": record["native_code"], "measure": record["measure"], "reference_year": record["reference_year"],
            "publication_date": record["publication_date"].isoformat() if record.get("publication_date") else None}


def evidence_status(record: Mapping[str, Any], registry: SourceRegistry, policy: PrecedencePolicy | None = None) -> dict[str, Any]:
    """Distinct qualification questions. Passing schema validation makes NOTHING operational."""
    policy = policy or PrecedencePolicy.load()
    src = registry.get(record["source_ref"]) or {}
    flags = {
        "schema_valid": True,
        "occupation_linked": bool(record.get("occupation_id")),
        "source_identified": bool(src.get("publisher") and src.get("dataset_name")),
        "licence_verified": src.get("licence_status") == "verified",
        "ingestion_approved": src.get("approval_status") in ("approved_for_ingestion", "approved_for_runtime_use"),
        "runtime_approved": registry.can_serve_as_evidence(record["source_ref"]),
        "measurement_qualified": record.get("qualification_status") == "qualified",
        "citation_available": build_citation(record, registry) is not None,
    }
    flags["operational"] = bool(flags["runtime_approved"] and flags["measurement_qualified"] and flags["citation_available"] and flags["occupation_linked"]
                                and record.get("value_status") == "reported" and policy.presentable(record.get("precedence_category"), record.get("evidence_class")))
    return flags


class CompensationStoreV2:
    def __init__(self, session_factory, registry: SourceRegistry, graph: OccupationGraph, policy: PrecedencePolicy | None = None) -> None:
        self._sf, self._reg, self._g = session_factory, registry, graph
        self.policy = policy or PrecedencePolicy.load()

    # ------------------------------------------------------------------------------------------------------------------------------- gate
    def _gate(self, source_ref: str, source_edition: str, mode: str) -> dict[str, Any]:
        src = self._reg.get(source_ref)
        if src is None:
            raise CompensationSourceNotApproved("the source is not registered")
        if mode == "production":
            if not self._reg.can_ingest(source_ref):
                raise CompensationSourceNotApproved("the source is not approved for ingestion (approval, verified licence and a genuine origin are required)")
            if (source_edition or "").strip().lower() in _UNKNOWN_EDITIONS:
                raise CompensationSourceNotApproved("the dataset edition must be known for a production import")
            if not src.get("publisher") or not src.get("dataset_name"):
                raise CompensationSourceNotApproved("source attribution is incomplete")
        elif mode == "fixture":
            if src["origin"] != "synthetic_fixture":
                raise CompensationSourceNotApproved("fixture mode needs a synthetic-fixture source")
            if not (source_edition or "").strip():
                raise CompensationSourceNotApproved("a source edition is required")
        else:
            raise CompensationSourceNotApproved("unknown import mode")
        if src.get("precedence_category") in (None, "unknown"):
            raise CompensationSourceNotApproved("the source has no precedence category")
        return src

    # ------------------------------------------------------------------------------------------------------------------------------ import
    def import_records(self, rows: Iterable[CompensationRecordV2 | Mapping[str, Any]], *, source_ref: str, source_edition: str, mode: str,
                       transformation: str | None = None, actor_user_id: int | None = None) -> ImportReport:
        src = self._gate(source_ref, source_edition, mode)
        rep = ImportReport(mode=mode, source_ref=source_ref, source_edition=source_edition)
        rej: Counter[str] = Counter()
        accepted: dict[str, tuple[CompensationRecordV2, dict[str, Any]]] = {}
        with self._sf() as s:
            tax_cache: dict[tuple[str, str], OccupationTaxonomy | None] = {}
            for raw in rows:
                rep.rows += 1
                try:
                    rec = raw if isinstance(raw, CompensationRecordV2) else CompensationRecordV2(**dict(raw))
                except (ValidationError, TypeError, ValueError) as exc:
                    loc = "unknown"
                    if isinstance(exc, ValidationError) and exc.errors():
                        loc = ".".join(str(x) for x in exc.errors()[0]["loc"]) or "model"
                    rej[f"schema_invalid:{loc}"] += 1
                    continue
                reason = self._reject_reason(s, rec, src, source_ref, source_edition, mode, tax_cache)
                if isinstance(reason, str):
                    rej[reason] += 1
                    continue
                node_id, tax, cls = reason
                key = record_key_for(rec, tax.id)
                prev = accepted.get(key)
                if prev is not None:
                    if prev[0].value == rec.value and prev[0].lower_value == rec.lower_value and prev[0].upper_value == rec.upper_value and prev[0].value_status == rec.value_status:
                        rep.existing += 1
                    else:
                        rej["conflicting_value_for_same_measurement"] += 1
                    continue
                accepted[key] = (rec, {"occupation_id": node_id, "taxonomy_id": tax.id, "evidence_class": cls})
            rep.batch_key = self._batch_key(source_ref, source_edition, mode, accepted, rej)
            if s.scalar(select(CompensationImportBatch.id).where(CompensationImportBatch.batch_key == rep.batch_key)) is not None:
                rep.already_imported, rep.existing, rep.rejected, rep.rejections = True, len(accepted), sum(rej.values()), dict(rej)
                return rep
            try:
                batch = CompensationImportBatch(batch_key=rep.batch_key, source_ref=source_ref, source_edition=source_edition, mode=mode, rejection_summary={}, transformation=(transformation or "")[:300],
                                                actor_user_id=actor_user_id)
                s.add(batch)
                s.flush()
                for key, (rec, link) in accepted.items():
                    state = self._insert(s, key, rec, link, src, batch.id)
                    if state == "added":
                        rep.added += 1
                    elif state == "existing":
                        rep.existing += 1
                    else:
                        rej["conflicting_value_for_same_measurement"] += 1
                rep.rejected, rep.rejections = sum(rej.values()), dict(rej)
                batch.records_added, batch.records_existing, batch.rows_rejected, batch.rejection_summary = rep.added, rep.existing, rep.rejected, dict(rej)
                s.commit()
            except IntegrityError:
                s.rollback()
                rep.already_imported, rep.added = True, 0                         # a concurrent identical import won the race: nothing is duplicated
            except Exception:
                s.rollback()
                raise
        return rep

    def _reject_reason(self, s, rec: CompensationRecordV2, src: dict[str, Any], source_ref: str, source_edition: str, mode: str, tax_cache):
        if rec.source_ref != source_ref or rec.source_edition != source_edition:
            return "source_mismatch"
        if mode == "production" and rec.taxonomy_edition.lower() in _UNKNOWN_EDITIONS:
            return "taxonomy_edition_unknown"
        tk = (rec.taxonomy_scheme, rec.taxonomy_edition)
        if tk not in tax_cache:
            tax_cache[tk] = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == tk[0], OccupationTaxonomy.edition == tk[1]))
        tax = tax_cache[tk]
        if tax is None:
            return "taxonomy_edition_not_registered"
        hits = self._g.find_by_identifier(rec.taxonomy_scheme, rec.native_code, rec.taxonomy_edition)
        keys = {h["occupation_key"] for h in hits}
        if not keys:
            return "occupation_not_in_graph"
        if len(keys) > 1:
            return "ambiguous_occupation_identity"
        if rec.earnings_concept == "household_income":
            return "earnings_concept_not_occupation_compensation"
        if rec.geography_level == "national" and rec.region:
            return "region_with_national_level"
        if rec.geography_level == "regional" and not rec.region:
            return "regional_level_without_region"
        cls = classify_evidence(self.policy, src.get("precedence_category"), rec.occupation_level, rec.geography_level)
        if cls is None:
            return "evidence_class_undeterminable"
        from src.persistence import GraphOccupation
        node_id = s.scalar(select(GraphOccupation.id).where(GraphOccupation.occupation_key == next(iter(keys))))
        return node_id, tax, cls

    @staticmethod
    def _batch_key(source_ref: str, source_edition: str, mode: str, accepted, rej: Counter) -> str:
        h = hashlib.sha256()
        h.update(f"{source_ref}\x1f{source_edition}\x1f{mode}".encode())
        for key in sorted(accepted):
            r = accepted[key][0]
            h.update(f"\x1e{key}\x1f{r.value}\x1f{r.lower_value}\x1f{r.upper_value}\x1f{r.value_status}".encode())
        h.update(("\x1d" + repr(sorted(rej.items()))).encode())
        return "cib_" + h.hexdigest()[:40]

    def _insert(self, s, key: str, rec: CompensationRecordV2, link: dict[str, Any], src: dict[str, Any], batch_id: int) -> str:
        existing = s.scalar(select(CompensationRecordV2Row).where(CompensationRecordV2Row.record_key == key))
        vals = row_values(rec)
        if existing is not None:
            same = from_row(existing)
            if same["value"] == rec.value and same["lower_value"] == rec.lower_value and same["upper_value"] == rec.upper_value and existing.value_status == rec.value_status:
                return "existing"
            return "conflict"
        s.add(CompensationRecordV2Row(
            record_key=key, occupation_id=link["occupation_id"], taxonomy_id=link["taxonomy_id"], native_code=rec.native_code, occupation_level=rec.occupation_level,
            link_basis="native_code_exact", country=rec.country, region_key=rec.region_key, geography_level=rec.geography_level, currency=rec.currency, pay_period=rec.pay_period,
            pay_basis=rec.pay_basis, measure=rec.measure, percentile=rec.percentile, earnings_concept=rec.earnings_concept, population_scope=rec.population_scope,
            evidence_method=rec.evidence_method, value_status=rec.value_status, bounds_semantic=rec.bounds_semantic, source_ref=rec.source_ref,
            source_edition=rec.source_edition, publisher=src.get("publisher"), dataset_name=src.get("dataset_name"), source_url=src.get("source_url"), reference_year=rec.reference_year,
            reference_period=rec.reference_period, publication_date=rec.publication_date, data_vintage=rec.data_vintage, evidence_class=link["evidence_class"],
            precedence_category=src["precedence_category"], qualification_status="unqualified", limitations=rec.limitations, provenance={**rec.provenance, "transformation_batch": batch_id},
            batch_id=batch_id, **vals))
        s.flush()
        return "added"

    # -------------------------------------------------------------------------------------------------------------------------------- reads
    def records_for(self, occupation_ids: Iterable[int], country: str, *, include_superseded: bool = False) -> list[dict[str, Any]]:
        """Index-backed lookup (occupation, country). Never scans the table."""
        ids = list(occupation_ids)
        if not ids:
            return []
        with self._sf() as s:
            stmt = select(CompensationRecordV2Row).where(CompensationRecordV2Row.occupation_id.in_(ids), CompensationRecordV2Row.country == country)
            if not include_superseded:
                stmt = stmt.where(CompensationRecordV2Row.status == "current")
            return [from_row(r) for r in s.scalars(stmt.order_by(CompensationRecordV2Row.id))]

    def set_qualification(self, record_key: str, status: str, *, actor_user_id: int | None) -> dict[str, Any]:
        """Measurement qualification (a named review). ``qualified`` needs a reviewer and a source of genuine origin; never callable from a candidate path."""
        from src.persistence import QUALIFICATION_STATUSES
        if status not in QUALIFICATION_STATUSES:
            raise ValueError("unknown qualification status")
        with self._sf() as s:
            r = s.scalar(select(CompensationRecordV2Row).where(CompensationRecordV2Row.record_key == record_key))
            if r is None:
                raise ValueError("unknown record")
            src = self._reg.get(r.source_ref) or {}
            if status == "qualified" and (actor_user_id is None or src.get("origin") not in E.EVIDENCE_ORIGINS):
                raise ValueError("qualification needs a named reviewer and a source of genuine origin")
            hist = list((r.provenance or {}).get("qualification_history", [])) + [{"from": r.qualification_status, "to": status, "actor_user_id": actor_user_id}]
            r.provenance = {**(r.provenance or {}), "qualification_history": hist}
            r.qualification_status = status
            s.commit()
            return from_row(r)

    def counts(self) -> dict[str, int]:
        from sqlalchemy import func
        with self._sf() as s:
            return {"records": s.scalar(select(func.count()).select_from(CompensationRecordV2Row)) or 0,
                    "batches": s.scalar(select(func.count()).select_from(CompensationImportBatch)) or 0}
