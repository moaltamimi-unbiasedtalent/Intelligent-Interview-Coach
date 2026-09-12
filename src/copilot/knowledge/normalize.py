"""Map existing source readers → the Phase 7A canonical build schema (Phase 7B).

Reuse-first: the parsing is done by the proven ``local_readers`` + ``normalisers``
(``NormalisedOccupation`` / the structured ``CompensationRecord``). This module only
*maps* those source-neutral records into the governed canonical build contract
(``canonical.py``): CanonicalOccupation, OccupationAlias, KnowledgeFact,
OccupationCrosswalk, CompensationRecord, LabourMarketRecord, SourceRecord — with stable
identity via ``CanonicalIdRegistry`` and full provenance.

Deterministic: ids/keys derive from source identity, never row order or timestamps. No
runtime/Agent code is touched; nothing here is imported by retrieval.
"""

from __future__ import annotations

import hashlib
from typing import Iterable

from src.copilot.knowledge import canonical as C
from src.copilot.knowledge.compensation import CompensationRecord as SrcComp
from src.copilot.knowledge.roles import NormalisedOccupation
from src.copilot.knowledge.structured_ext import (
    LabourForecast,
    LabourOpenings,
    LabourShortage,
    LabourVacancy,
)

# Which classification a source's native occupation_code represents.
_SOURCE_CLASSIFICATION = {
    "onet": C.ClassificationScheme.ONET_SOC,
    "esco": C.ClassificationScheme.ESCO,
    "isco08": C.ClassificationScheme.ISCO,
    "kldb": C.ClassificationScheme.KLDB,
    "bls_ooh": C.ClassificationScheme.SOC,
    "bls_projections": C.ClassificationScheme.SOC,
}
_SCHEME_BY_NAME = {s.value: s for s in C.ClassificationScheme}


def _short(*parts: str) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _id_kwargs(occ: NormalisedOccupation) -> dict:
    """Identity kwargs for CanonicalIdRegistry.resolve_or_assign.

    CRITICAL (§32/§34): an occupation's identity key is ONLY its own native-scheme code.
    A cross-scheme code such as ``occ.isco_code`` is a *broader group* (ISCO unit groups are
    shared by many ESCO/O*NET occupations) — using it as an identity key would silently
    merge every occupation under that group. Such codes flow to crosswalks and to the
    ``classifications``/``isco_code`` columns, never to the identity registry. The
    (source, source_occupation_id) native fallback keeps a source-local record identifiable
    without enabling cross-source merges (that is Phase 7B canonicalization proper)."""
    kw: dict[str, str] = {"source": occ.source_id, "source_occupation_id": occ.occupation_code}
    sch = _SOURCE_CLASSIFICATION.get(occ.source_id)
    code = occ.occupation_code
    if sch is C.ClassificationScheme.ESCO:
        kw["esco_uri"] = code
    elif sch is C.ClassificationScheme.ONET_SOC:
        kw["onet_soc_code"] = code
    elif sch is C.ClassificationScheme.ISCO:
        kw["isco_code"] = code
    elif sch is C.ClassificationScheme.KLDB:
        kw["kldb_code"] = code
    elif sch is C.ClassificationScheme.SOC:
        kw["soc_code"] = code
    return kw


def _provenance_bits(occ: NormalisedOccupation, source_meta: dict | None = None) -> dict:
    """Provenance fields for an occupation: the record's own ``Provenance`` when present,
    otherwise governed per-source metadata (manifest ``source_url``/``licence``/``version``/
    ``language``/``country``/``reference_year``). Readers currently leave ``provenance`` unset,
    so ``source_meta`` (from :func:`source_meta_from_manifest`) is the normal path."""
    out = {"source_url": None, "license": None, "source_version": None,
           "country": None, "language": None, "reference_year": None}
    p = occ.provenance
    if p:
        out.update({
            "source_url": getattr(p, "source_url", None),
            "license": getattr(p, "licence", None),
            "source_version": getattr(p, "version", None),
            "country": getattr(p, "country", None),
            "language": getattr(p, "language", None),
            "reference_year": getattr(p, "reference_year", None),
        })
    for k, v in (source_meta or {}).items():
        if v is not None and out.get(k) is None:
            out[k] = v
    return out


def source_meta_from_manifest(entry) -> dict:
    """Map a manifest ``SourceEntry`` to the provenance dict the mappers consume."""
    if entry is None:
        return {}
    return {"source_url": entry.source_url, "license": entry.licence,
            "source_version": entry.version, "country": entry.country,
            "language": entry.language, "reference_year": entry.reference_year}


def occupation_to_canonical(occ: NormalisedOccupation, registry: C.CanonicalIdRegistry,
                            *, raw_file: str | None = None, source_meta: dict | None = None):
    """Return (CanonicalOccupation, [OccupationAlias], [KnowledgeFact], [OccupationCrosswalk],
    [OccupationRelationship], SourceRecord) for one source occupation. Identity is assigned/
    looked-up via the registry so it stays stable as later sources enrich the same occupation.

    Career scalar attributes (entry_education, work_experience, on_the_job_training, outlook)
    are emitted as typed KnowledgeFacts carrying ``metadata['attribute']`` so the runtime build
    can reconstruct the occupation_attributes store losslessly. Same-source occupation→occupation
    links (related/parent/similar) are emitted as OccupationRelationship (kept distinct from
    cross-scheme OccupationCrosswalk)."""
    pv = _provenance_bits(occ, source_meta)
    oid = registry.resolve_or_assign(**_id_kwargs(occ))
    src_rec_id = f"{occ.source_id}:{occ.occupation_code}"
    sch = _SOURCE_CLASSIFICATION.get(occ.source_id)

    geography = None
    if pv.get("country"):
        geography = C.Geography(geography_type=C.GeographyType.COUNTRY, country=pv["country"])
    temporal = C.TemporalMetadata(source_version=pv.get("source_version"),
                                  reference_year=pv.get("reference_year")) \
        if (pv.get("source_version") or pv.get("reference_year")) else None

    classifications = []
    # Scheme-native code columns (isco is handled once, below, to avoid a duplicate kwarg
    # when the source IS ISCO and also carries occ.isco_code).
    kw = {}
    isco_value = occ.isco_code or None
    if sch is C.ClassificationScheme.ESCO:
        kw["esco_uri"] = occ.occupation_code
    elif sch is C.ClassificationScheme.ONET_SOC:
        kw["onet_soc_code"] = occ.occupation_code
    elif sch is C.ClassificationScheme.ISCO:
        isco_value = occ.occupation_code
    elif sch is C.ClassificationScheme.KLDB:
        kw["kldb_code"] = occ.occupation_code
    elif sch is C.ClassificationScheme.SOC:
        kw["soc_code"] = occ.occupation_code
    if sch:
        classifications.append(C.ClassificationRef(scheme=sch, code=occ.occupation_code))
    if occ.isco_code and sch is not C.ClassificationScheme.ISCO:
        classifications.append(C.ClassificationRef(scheme=C.ClassificationScheme.ISCO,
                                                   code=occ.isco_code))

    source_record = C.SourceRecord(
        source_record_id=src_rec_id, source=occ.source_id, record_type="occupation",
        source_identifier=occ.occupation_code, source_title=occ.title,
        source_url=pv.get("source_url"), license=pv.get("license"),
        source_version=pv.get("source_version"), language=pv.get("language"),
        geography=geography, raw_file=raw_file,
    )

    canonical = C.CanonicalOccupation(
        occupation_id=oid, canonical_title=occ.title, description=occ.description,
        source=occ.source_id, source_version=pv.get("source_version"),
        source_occupation_id=occ.occupation_code, source_record_id=src_rec_id,
        preferred_label=occ.title, language=pv.get("language"),
        isco_code=isco_value, source_url=pv.get("source_url"),
        license=pv.get("license"), geography=geography, temporal=temporal,
        classifications=classifications, **kw,
    )

    aliases = []
    seen_alias = set()
    for a in occ.aliases:
        na = C.normalize_text(a)
        if not na or na in seen_alias:
            continue
        seen_alias.add(na)
        aliases.append(C.OccupationAlias(
            alias=a, normalized_alias=na, canonical_occupation_id=oid,
            canonical_title=occ.title, source=occ.source_id,
            source_version=pv.get("source_version"), source_occupation_id=occ.occupation_code,
            language=pv.get("language"), relationship=C.AliasRelationship.ALTERNATIVE_TITLE,
            confidence=C.ConfidenceBasis.SOURCE_DIRECT,
            source_record_id=src_rec_id))

    facts = []

    def _fact(ftype: C.FactType, value: str, meta: dict | None = None):
        if not value or not value.strip():
            return
        facts.append(C.KnowledgeFact(
            fact_id=f"{occ.source_id}:{_short(occ.occupation_code, ftype.value, value)}",
            occupation_id=oid, canonical_title=occ.title, fact_type=ftype,
            fact_value=value.strip(), source=occ.source_id,
            source_version=pv.get("source_version"), source_record_id=src_rec_id,
            source_url=pv.get("source_url"), license=pv.get("license"),
            language=pv.get("language"), confidence=C.ConfidenceBasis.SOURCE_DIRECT,
            metadata=meta or {}))

    for s in occ.skills:
        ftype = C.FactType.TECHNOLOGY_SKILL if s.skill_type == "technology" else C.FactType.SKILL
        _fact(ftype, s.name, {"relation": s.skill_type})
    for k in occ.knowledge:
        _fact(C.FactType.KNOWLEDGE, k)
    for t in occ.tasks:
        _fact(C.FactType.TASK, t)
    for a in occ.activities:
        _fact(C.FactType.WORK_ACTIVITY, a)
    # Career scalar attributes → typed facts tagged for lossless attribute reconstruction.
    _fact(C.FactType.EDUCATION, occ.entry_education or "", {"attribute": "entry_education"})
    _fact(C.FactType.WORK_EXPERIENCE, occ.work_experience or "", {"attribute": "work_experience"})
    _fact(C.FactType.TRAINING, occ.on_the_job_training or "", {"attribute": "on_the_job_training"})
    _fact(C.FactType.FORECAST, occ.outlook or "", {"attribute": "outlook"})

    relationships = []
    for r in occ.relationships:
        if not r.related_code:
            continue
        relationships.append(C.OccupationRelationship(
            relationship_id=f"{occ.source_id}:{_short(occ.occupation_code, r.relation_type, r.related_code)}",
            occupation_id=oid, source_occupation_id=occ.occupation_code,
            related_code=r.related_code, relation_type=r.relation_type,
            source=occ.source_id, source_version=pv.get("source_version"),
            source_record_id=src_rec_id))

    crosswalks = []
    # Inherent: an O*NET-SOC / SOC / KldB / ISCO occupation IS a code in its own scheme —
    # no crosswalk needed. Emit crosswalks only for cross-scheme mappings the source states.
    for m in occ.mappings:
        tsch = _SCHEME_BY_NAME.get(m.scheme)
        if not tsch or tsch is sch:
            continue
        crosswalks.append(C.OccupationCrosswalk(
            crosswalk_id=f"{occ.source_id}:{_short(occ.occupation_code, m.scheme, m.code)}",
            source_occupation_id=oid, target_occupation_id=f"{m.scheme}:{m.code}",
            source_classification=sch or C.ClassificationScheme.ESCO,
            target_classification=tsch, source_code=occ.occupation_code, target_code=m.code,
            mapping_type=C.MappingType.EXACT if tsch is C.ClassificationScheme.ISCO
            else C.MappingType.RELATED,
            mapping_strength=C.MappingStrength.OFFICIAL, official_mapping=True,
            source=occ.source_id, source_version=pv.get("source_version")))

    return canonical, aliases, facts, crosswalks, relationships, source_record


_STAT = {"median": C.CompensationStatistic.MEDIAN, "mean": C.CompensationStatistic.MEAN,
         "p10": C.CompensationStatistic.P10, "p25": C.CompensationStatistic.P25,
         "p50": C.CompensationStatistic.P50, "p75": C.CompensationStatistic.P75,
         "p90": C.CompensationStatistic.P90}
_PERIOD = {"annual": C.PayPeriod.YEAR, "year": C.PayPeriod.YEAR,
           "monthly": C.PayPeriod.MONTH, "month": C.PayPeriod.MONTH,
           "weekly": C.PayPeriod.WEEK, "week": C.PayPeriod.WEEK,
           "hourly": C.PayPeriod.HOUR, "hour": C.PayPeriod.HOUR}
# SOC-classified compensation sources (US SOC / UK SOC codes carried on the record).
_SOC_COMP_SOURCES = ("bls_oews", "ons_ashe")


def compensation_to_canonical(rec: SrcComp, registry: C.CanonicalIdRegistry,
                              *, source_meta: dict | None = None):
    """Map the structured source CompensationRecord → canonical CompensationRecord.

    Semantics preserved verbatim (statistic / pay_period / currency / year); NEVER
    converts hourly↔weekly↔annual or gross↔net. The source-native pay period is ALWAYS
    retained in metadata so nothing is lost even when the typed enum cannot represent it.
    ``retrieved_at`` is left unset here: the acquisition date lives with the raw source's
    provenance sidecar, and stamping normalize-time would break deterministic rebuilds (§4).
    Returns (record, reject_reason|None)."""
    stat = _STAT.get((rec.statistic_type or "").lower())
    native_period = (rec.pay_period or "").strip().lower() or None
    period = _PERIOD.get(native_period)
    if not rec.currency:
        return None, "unknown_currency"
    if rec.value is None:
        return None, "invalid_amount"
    meta = source_meta or {}
    # Link to a canonical occupation only via an existing native-code mapping (no fuzzy title).
    oid = None
    if rec.occupation_code:
        oid = registry.get(soc_code=rec.occupation_code)
    country = rec.country or meta.get("country") or None
    classification = C.ClassificationScheme.SOC if rec.source_id in _SOC_COMP_SOURCES else None
    comp_id = f"{rec.source_id}:{_short(rec.occupation_code or '', rec.geography, str(rec.year), rec.statistic_type, rec.pay_period)}"
    return C.CompensationRecord(
        compensation_id=comp_id, occupation_id=oid,
        source_occupation_id=rec.occupation_code, occupation_code=rec.occupation_code,
        classification=classification, country=country, region=rec.region,
        geography_type=C.GeographyType.COUNTRY if country else None,
        industry=rec.industry, currency=rec.currency, amount=float(rec.value),
        statistic=stat, pay_period=period, gross_net=C.GrossNet.UNKNOWN,
        compensation_type=C.CompensationType.OBSERVED_EARNINGS,
        effective_year=rec.year, source=rec.source_id,
        source_version=meta.get("source_version"),
        source_record_id=comp_id, source_url=rec.source_url or meta.get("source_url"),
        source_quality=C.SourceQualityCategory.OFFICIAL_STATISTICS,
        metadata={"lower_bound": rec.lower_bound, "upper_bound": rec.upper_bound,
                  "sample_quality": rec.sample_quality, "geography": rec.geography,
                  "pay_period_native": native_period}), None


# --- Labour-market mappers (structured_ext → canonical LabourMarketRecord) -------------
# Geography is classified deterministically so DE / EU / US / UK stay SEPARATE (§57): an EU
# or Euro-area aggregate is never written to the country field, and a sub-national NUTS region
# is a REGION (never conflated with, nor silently rolled up into, its country). The raw label
# is always retained verbatim in metadata.geography_label — nothing is lost.

# Well-known country NAMES (Eurostat/Cedefop labels) → ISO-2. Deterministic, additive.
_COUNTRY_NAMES = {
    "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT", "netherlands": "NL",
    "belgium": "BE", "austria": "AT", "portugal": "PT", "sweden": "SE", "finland": "FI",
    "denmark": "DK", "norway": "NO", "ireland": "IE", "luxembourg": "LU", "greece": "GR",
    "czechia": "CZ", "czech republic": "CZ", "hungary": "HU", "romania": "RO",
    "bulgaria": "BG", "slovakia": "SK", "slovenia": "SI", "croatia": "HR", "poland": "PL",
    "lithuania": "LT", "latvia": "LV", "estonia": "EE", "cyprus": "CY", "malta": "MT",
    "iceland": "IS", "switzerland": "CH", "united kingdom": "UK", "united states": "US",
}
_AGG_MARKERS = ("european union", "euro area", "european economic area")


def _geo(value: str | None) -> dict:
    """Classify a source geography string into typed canonical geography fields.

    Returns kwargs for LabourMarketRecord: country / region / geography_type, plus a
    ``geography_label`` (the raw value) for metadata. ISO-2 codes and known country names
    resolve to a country; EU/Euro-area aggregates and other labels (NUTS regions) resolve to
    a REGION with country left None (§57)."""
    v = (value or "").strip()
    if not v:
        return {"country": None, "region": None, "geography_type": None, "label": None}
    low = v.lower()
    if len(v) == 2 and v.isalpha():
        return {"country": v, "region": None,
                "geography_type": C.GeographyType.COUNTRY, "label": v}
    if low in _COUNTRY_NAMES:
        return {"country": _COUNTRY_NAMES[low], "region": None,
                "geography_type": C.GeographyType.COUNTRY, "label": v}
    if any(m in low for m in _AGG_MARKERS) or v.upper().startswith(("EU2", "EU28", "EA1", "EA2")):
        return {"country": None, "region": None,
                "geography_type": C.GeographyType.REGION, "label": v}  # supra-national aggregate
    return {"country": None, "region": v,
            "geography_type": C.GeographyType.REGION, "label": v}      # sub-national / other


def labour_forecast_to_canonical(f: LabourForecast, *, source_meta: dict | None = None):
    meta = source_meta or {}
    g = _geo(f.country)
    lm_id = f"{f.source_id}:fc:{_short(f.occupation, f.country, f.horizon or '', str(f.reference_year))}"
    return C.LabourMarketRecord(
        labour_market_id=lm_id, country=g["country"], region=g["region"],
        geography_type=g["geography_type"],
        metric_type=C.MetricType.GROWTH_RATE, value=f.employment_change, unit="fraction",
        forecast_period=f.horizon, source=f.source_id, source_version=meta.get("source_version"),
        source_record_id=lm_id, source_url=meta.get("source_url"),
        source_quality=C.SourceQualityCategory.OFFICIAL_LABOUR_MARKET,
        metadata={"occupation": f.occupation, "sector": f.sector,
                  "replacement_demand": f.replacement_demand,
                  "reference_year": f.reference_year, "geography_label": g["label"]})


def labour_openings_to_canonical(o: LabourOpenings, *, source_meta: dict | None = None):
    meta = source_meta or {}
    g = _geo(o.geography)
    lm_id = f"{o.source_id}:op:{_short(o.occupation, o.geography, o.period or '')}"
    return C.LabourMarketRecord(
        labour_market_id=lm_id, country=g["country"], region=g["region"],
        geography_type=g["geography_type"],
        metric_type=C.MetricType.JOB_OPENINGS, value=o.total_openings, unit="count",
        forecast_period=o.period, source=o.source_id, source_version=meta.get("source_version"),
        source_record_id=lm_id, source_url=meta.get("source_url"),
        source_quality=C.SourceQualityCategory.OFFICIAL_LABOUR_MARKET,
        metadata={"occupation": o.occupation, "new_jobs": o.new_jobs,
                  "replacement_demand": o.replacement_demand, "geography_label": g["label"]})


def labour_shortage_to_canonical(s: LabourShortage, *, source_meta: dict | None = None):
    meta = source_meta or {}
    g = _geo(s.country)
    # Full-content key: CLSSI emits one row per (country, occupation group) and the
    # distinguishing detail is the skill level + shortage indicator — include them so
    # genuinely distinct shortage records are preserved (only true content-dupes collapse, §50).
    lm_id = (f"{s.source_id}:sh:"
             f"{_short(s.occupation, s.country, s.period or '', s.skill_level or '', s.shortage_indicator or '')}")
    return C.LabourMarketRecord(
        labour_market_id=lm_id, country=g["country"], region=g["region"],
        geography_type=g["geography_type"],
        metric_type=C.MetricType.SHORTAGE_INDICATOR, value=None, unit=None,
        effective_period=s.period, source=s.source_id, source_version=meta.get("source_version"),
        source_record_id=lm_id, source_url=meta.get("source_url"),
        source_quality=C.SourceQualityCategory.OFFICIAL_LABOUR_MARKET,
        metadata={"occupation": s.occupation, "skill_level": s.skill_level,
                  "shortage_indicator": s.shortage_indicator, "geography_label": g["label"]})


def labour_vacancy_to_canonical(v: LabourVacancy, *, source_meta: dict | None = None):
    meta = source_meta or {}
    g = _geo(v.country)
    region = v.region or g["region"]
    lm_id = f"{v.source_id}:vac:{_short(v.occupation, v.country, str(v.year), v.indicator or '')}"
    return C.LabourMarketRecord(
        labour_market_id=lm_id, country=g["country"], region=region,
        geography_type=g["geography_type"],
        metric_type=C.MetricType.VACANCIES, value=v.value, unit=v.unit,  # rate or count
        effective_period=str(v.year) if v.year else None,
        source=v.source_id, source_version=meta.get("source_version"),
        source_record_id=lm_id, source_url=meta.get("source_url"),
        source_quality=C.SourceQualityCategory.OFFICIAL_LABOUR_MARKET,
        metadata={"occupation": v.occupation, "indicator": v.indicator,
                  "experimental": v.experimental, "reference_year": v.year,
                  "geography_label": g["label"]})


def competency_source_record(comp, *, raw_file: str | None = None,
                             source_meta: dict | None = None) -> C.SourceRecord:
    """A provenance record for one framework competency (NICE/DigComp).

    Competencies are framework-level, NOT occupation-linked (§28–31: NICE work-role identity
    stays separate from occupations; no auto-equate to O*NET). They are emitted as their own
    ``competencies`` output (the source ``Competency`` rows) each backed by this SourceRecord."""
    meta = source_meta or {}
    rid = f"{comp.source_id}:{_short(comp.framework, comp.area, comp.name)}"
    return C.SourceRecord(
        source_record_id=rid, source=comp.source_id, record_type="competency",
        source_identifier=comp.name[:120], source_title=comp.name,
        source_url=meta.get("source_url"), license=meta.get("license"),
        source_version=meta.get("source_version"), language=meta.get("language"),
        raw_file=raw_file, metadata={"framework": comp.framework, "area": comp.area})


def dedupe(records: Iterable, key) -> list:
    """Deterministic dedup by a semantic key; input order preserved for the survivor."""
    seen = set()
    out = []
    for r in records:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out
