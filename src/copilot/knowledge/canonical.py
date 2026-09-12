"""Canonical knowledge-build data contract (Phase 7A).

This module defines the **build-layer** schema for the reproducible, multi-source
knowledge foundation — the typed contract that the Phase 7B loaders will emit into
``data/normalized/`` and that later phases merge into the runtime structured stores.

It is deliberately SEPARATE from the runtime models:

* Runtime retrieval already has ``Provenance`` (``knowledge/provenance.py``),
  ``KnowledgeEvidence`` and ``Citation`` (``copilot/models.py``), and the per-source
  ``NormalisedOccupation`` (``knowledge/roles.py``). Those describe what retrieval
  returns to the candidate path and are unchanged.
* This module describes the *cross-source, provenance-preserving intermediate* used to
  REBUILD those stores deterministically: canonical occupation identity, aliases with
  typed relationships, provenance-aware facts, exact raw-input source records, and the
  geography / temporal / seniority / confidence context dimensions — plus build
  reproducibility metadata.

Nothing here is imported by the FastAPI runtime or the retrieval path. The optional
Parquet helpers lazy-import ``pyarrow`` (``pip install -e ".[knowledge]"``); JSONL is the
always-available fallback so the base install and tests work without pyarrow.

No behaviour change to the current KB: this is schema/contract only.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


__all__ = [
    "CANONICAL_SCHEMA_VERSION",
    "ClassificationScheme",
    "AliasRelationship",
    "FactType",
    "ConfidenceBasis",
    "Seniority",
    "GeographyType",
    "ClassificationRef",
    "Geography",
    "TemporalMetadata",
    "SourceFingerprint",
    "SourceRecord",
    "CanonicalOccupation",
    "OccupationAlias",
    "KnowledgeFact",
    "BuildMetadata",
    "ASK4MO_CURATED_SOURCE",
    "normalize_text",
    "sha256_file",
    "canonical_occupation_id",
    "write_jsonl",
    "read_jsonl",
    "write_parquet",
    "read_parquet",
    "ParquetUnavailableError",
]

# Bump when the canonical build-layer schema changes shape (drives build_metadata and
# lets a rebuild detect an incompatible normalized layer).
CANONICAL_SCHEMA_VERSION = 1

# Curated Ask4Mo-authored data must always be attributable and must NEVER masquerade as
# an official source (§12).
ASK4MO_CURATED_SOURCE = "ask4mo_curated"


# --------------------------------------------------------------------------------------
# Controlled vocabularies (§11 relationships, §13 fact types, §17 seniority, §18 confidence)
# --------------------------------------------------------------------------------------

class ClassificationScheme(str, Enum):
    """External occupation classification systems used for cross-source identity."""

    ESCO = "esco"          # ESCO occupation URI
    ONET_SOC = "onet_soc"  # O*NET-SOC code
    SOC = "soc"            # US SOC code
    ISCO = "isco"          # ISCO-08 code
    KLDB = "kldb"          # German KldB 2010 code


class AliasRelationship(str, Enum):
    """How an alias relates to its canonical occupation (aliases are NOT equivalent)."""

    PREFERRED_TITLE = "preferred_title"
    ALTERNATIVE_TITLE = "alternative_title"
    SYNONYM = "synonym"
    BROADER_TITLE = "broader_title"
    NARROWER_TITLE = "narrower_title"
    CLASSIFICATION_MAPPING = "classification_mapping"
    CURATED_ALIAS = "curated_alias"


class FactType(str, Enum):
    """Kinds of provenance-aware knowledge fact.

    Superset aligned with the runtime ``KnowledgeEvidence.evidence_type`` vocabulary so a
    normalized fact maps cleanly onto downstream evidence without a lossy translation.
    """

    SKILL = "skill"
    RESPONSIBILITY = "responsibility"
    TASK = "task"
    KNOWLEDGE = "knowledge"
    ABILITY = "ability"
    COMPETENCY = "competency"
    QUALIFICATION = "qualification"
    CREDENTIAL = "credential"
    TECHNOLOGY_SKILL = "technology_skill"
    WORK_ACTIVITY = "work_activity"
    WORK_CONTEXT = "work_context"
    EDUCATION = "education"
    TRAINING = "training"
    WORK_EXPERIENCE = "work_experience"
    WAGE = "wage"
    EMPLOYMENT = "employment"
    FORECAST = "forecast"


class ConfidenceBasis(str, Enum):
    """WHY a normalized relation is trusted — a provenance kind, not a fake 0–1 score (§18).

    Official-source facts are ``source_direct`` and are not assigned invented uncertainty.
    An optional numeric ``confidence_score`` may accompany a fact ONLY where a source
    genuinely provides one; its meaning must be documented by the producing loader.
    """

    SOURCE_DIRECT = "source_direct"                  # stated directly by the source
    OFFICIAL_MAPPING = "official_mapping"            # an official taxonomy crosswalk
    DERIVED_NORMALIZATION = "derived_normalization"  # deterministic transform we applied
    CURATED_MANUAL = "curated_manual"                # Ask4Mo-authored mapping


class Seniority(str, Enum):
    """Seniority as a separate context dimension (§17). Normalization behaviour is 7B."""

    ENTRY = "entry"
    JUNIOR = "junior"
    ASSOCIATE = "associate"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    STAFF = "staff"
    PRINCIPAL = "principal"
    MANAGER = "manager"
    DIRECTOR = "director"
    HEAD = "head"
    VICE_PRESIDENT = "vice_president"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class GeographyType(str, Enum):
    """Granularity of a geography reference."""

    GLOBAL = "global"
    COUNTRY = "country"
    REGION = "region"       # supra-national (e.g. EU) or intra-national macro region
    SUBREGION = "subregion"
    STATE = "state"
    METRO = "metro"


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    """Deterministic normalization for alias/title matching keys (lowercase, collapsed
    whitespace, punctuation trimmed). Kept intentionally simple; richer title
    canonicalization is Phase 7B."""
    if not value:
        return ""
    cleaned = re.sub(r"[^\w\s&/+-]", " ", value.lower())
    return _WS_RE.sub(" ", cleaned).strip()


def sha256_file(path: str | Path, *, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file, streamed so large raw inputs are not read into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()


def canonical_occupation_id(
    *,
    esco_uri: str | None = None,
    onet_soc_code: str | None = None,
    isco_code: str | None = None,
    soc_code: str | None = None,
    kldb_code: str | None = None,
    source: str | None = None,
    source_occupation_id: str | None = None,
) -> str:
    """Derive a STABLE Ask4Mo canonical occupation id: ``ask4mo:occ:<16-hex>``.

    Stability rules (documented so rebuilds are reproducible):

    * The id is a SHA-256 over a single ``scheme:value`` key — never a row number, file
      order or ingestion timestamp — so the same occupation yields the same id across
      rebuilds and across machines.
    * The key is chosen by a fixed classification precedence, most-stable first:
      ESCO URI → O*NET-SOC → ISCO → SOC → KldB. This prefers a durable public
      classification over a source-local id.
    * Only when NO classification code is available do we fall back to the source-native
      identity (``source:source_occupation_id``). Such ids are still stable for that
      source but cannot yet be merged across sources — cross-source merging is Phase 7B
      and is intentionally NOT performed here.

    Raises ``ValueError`` if there is no usable key (never returns a fabricated id).
    """
    key: str | None = None
    if esco_uri:
        key = f"{ClassificationScheme.ESCO.value}:{esco_uri.strip()}"
    elif onet_soc_code:
        key = f"{ClassificationScheme.ONET_SOC.value}:{onet_soc_code.strip().lower()}"
    elif isco_code:
        key = f"{ClassificationScheme.ISCO.value}:{str(isco_code).strip()}"
    elif soc_code:
        key = f"{ClassificationScheme.SOC.value}:{str(soc_code).strip()}"
    elif kldb_code:
        key = f"{ClassificationScheme.KLDB.value}:{str(kldb_code).strip()}"
    elif source and source_occupation_id:
        key = f"native:{source.strip()}:{source_occupation_id.strip()}"
    if not key:
        raise ValueError(
            "canonical_occupation_id needs at least one classification code or a "
            "(source, source_occupation_id) pair — refusing to fabricate an id."
        )
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"ask4mo:occ:{digest}"


# --------------------------------------------------------------------------------------
# Context dimensions
# --------------------------------------------------------------------------------------

class ClassificationRef(BaseModel):
    """A single external classification code for cross-source identity/crosswalks (§8)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    scheme: ClassificationScheme
    code: str = Field(min_length=1)


class Geography(BaseModel):
    """Structured geography so, e.g., US BLS wages can never be read as DE pay (§15)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    geography_type: GeographyType = GeographyType.COUNTRY
    country: str | None = Field(default=None, description="ISO-3166 alpha-2 where known.")
    region: str | None = None       # e.g. EU, or a national macro region
    subregion: str | None = None
    state: str | None = None
    metro: str | None = None
    geography_code: str | None = Field(default=None, description="Source geography code.")

    @field_validator("country")
    @classmethod
    def _upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class TemporalMetadata(BaseModel):
    """Distinguish source version, effective period, record year and retrieval date (§16).

    So "2025 wage data downloaded in 2026" is never mislabelled as 2026 data.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_version: str | None = Field(default=None, description="Dataset release/version.")
    effective_period: str | None = Field(
        default=None, description="Period the data DESCRIBES, e.g. '2022-2035' or 'FY2025'."
    )
    reference_year: int | None = Field(
        default=None, ge=1900, le=2100, description="Year the record refers to."
    )
    retrieved_at: date | None = Field(default=None, description="When the file was acquired.")


class SourceFingerprint(BaseModel):
    """Deterministic identity of a consumed raw input (§7). Relative paths only (§7/§24)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    algorithm: str = "sha256"
    relative_path: str = Field(min_length=1, description="Path relative to the repo root.")
    hash: str = Field(min_length=8)

    @field_validator("relative_path")
    @classmethod
    def _reject_absolute(cls, v: str) -> str:
        if v.startswith("/") or (len(v) > 1 and v[1] == ":"):
            raise ValueError("SourceFingerprint.relative_path must not be machine-absolute.")
        return v


# --------------------------------------------------------------------------------------
# Provenance-preserving records
# --------------------------------------------------------------------------------------

class SourceRecord(BaseModel):
    """Ties a normalized row back to the EXACT raw input it came from (§14).

    Every canonical occupation / alias / fact references a ``source_record_id`` so any
    downstream fact can be traced to its authoritative origin. ``raw_row_identifier`` is
    a best-effort locator and is NOT treated as permanent identity when source row order
    may change — the ``source_fingerprint`` + ``source_identifier`` are the durable keys.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_record_id: str = Field(min_length=1)
    source: str = Field(min_length=1, description="Manifest source_id, or ask4mo_curated.")
    source_version: str | None = None
    record_type: str = Field(description="e.g. occupation | alias | skill_relation | wage.")

    source_identifier: str | None = Field(
        default=None, description="Durable native id/URI within the source, when present."
    )
    source_title: str | None = None
    source_url: str | None = None
    license: str | None = None

    geography: Geography | None = None
    language: str | None = None
    temporal: TemporalMetadata | None = None

    raw_file: str | None = Field(default=None, description="Relative raw path.")
    raw_sheet: str | None = None
    raw_row_identifier: str | None = Field(
        default=None, description="Best-effort row locator; not a permanent id."
    )
    source_fingerprint: SourceFingerprint | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_file")
    @classmethod
    def _rel_raw(cls, v: str | None) -> str | None:
        if v and (v.startswith("/") or (len(v) > 1 and v[1] == ":")):
            raise ValueError("SourceRecord.raw_file must be a repo-relative path.")
        return v


class CanonicalOccupation(BaseModel):
    """A canonical occupation row for the normalized layer (§10).

    Not every source populates every field — Optional/None is used rather than fake
    defaults. Cross-source merging is NOT performed in Phase 7A: each row keeps its
    source-native identity alongside the derived canonical id.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    occupation_id: str = Field(description="Stable ask4mo:occ:<hash> canonical id.")
    canonical_title: str = Field(min_length=1)
    description: str | None = None

    source: str = Field(min_length=1)
    source_version: str | None = None
    source_occupation_id: str | None = None
    source_record_id: str

    preferred_label: str | None = None
    language: str | None = None

    isco_code: str | None = None
    soc_code: str | None = None
    onet_soc_code: str | None = None
    esco_uri: str | None = None
    kldb_code: str | None = None
    classifications: list[ClassificationRef] = Field(default_factory=list)

    geography: Geography | None = None
    seniority: Seniority | None = None
    industry: str | None = None

    source_url: str | None = None
    license: str | None = None
    temporal: TemporalMetadata | None = None

    @field_validator("occupation_id")
    @classmethod
    def _canonical_prefix(cls, v: str) -> str:
        if not v.startswith("ask4mo:occ:"):
            raise ValueError("occupation_id must be an ask4mo:occ:<hash> canonical id.")
        return v


class OccupationAlias(BaseModel):
    """A first-class alias record — aliases are typed, not all equivalent (§11/§12)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    alias: str = Field(min_length=1)
    normalized_alias: str = Field(min_length=1)
    canonical_occupation_id: str
    canonical_title: str | None = None

    source: str = Field(min_length=1)
    source_version: str | None = None
    source_occupation_id: str | None = None
    source_record_id: str

    language: str | None = None
    relationship: AliasRelationship = AliasRelationship.ALTERNATIVE_TITLE
    confidence: ConfidenceBasis = ConfidenceBasis.SOURCE_DIRECT

    @field_validator("canonical_occupation_id")
    @classmethod
    def _canonical_prefix(cls, v: str) -> str:
        if not v.startswith("ask4mo:occ:"):
            raise ValueError("canonical_occupation_id must be an ask4mo:occ:<hash> id.")
        return v

    @field_validator("confidence")
    @classmethod
    def _curated_marked(cls, v: ConfidenceBasis, info) -> ConfidenceBasis:
        # A curated alias must declare a curated source (never masquerade as official).
        src = (info.data.get("source") or "")
        if v == ConfidenceBasis.CURATED_MANUAL and src != ASK4MO_CURATED_SOURCE:
            raise ValueError(
                f"curated_manual aliases must have source='{ASK4MO_CURATED_SOURCE}'."
            )
        return v


class KnowledgeFact(BaseModel):
    """A provenance-aware fact about an occupation (§13).

    Facts are typed (``FactType``), attributed (``source`` + ``source_record_id``),
    contextual (geography / seniority / industry / temporal) and traceable
    (``source_url`` + ``license``).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    fact_id: str = Field(min_length=1)
    occupation_id: str
    canonical_title: str | None = None

    fact_type: FactType
    fact_value: str = Field(min_length=1)

    source: str = Field(min_length=1)
    source_version: str | None = None
    source_record_id: str

    geography: Geography | None = None
    seniority: Seniority | None = None
    industry: str | None = None
    language: str | None = None
    temporal: TemporalMetadata | None = None

    source_url: str | None = None
    license: str | None = None

    confidence: ConfidenceBasis = ConfidenceBasis.SOURCE_DIRECT
    confidence_score: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Optional numeric confidence ONLY where a source provides one; its "
        "meaning must be documented by the producing loader.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occupation_id")
    @classmethod
    def _canonical_prefix(cls, v: str) -> str:
        if not v.startswith("ask4mo:occ:"):
            raise ValueError("occupation_id must be an ask4mo:occ:<hash> canonical id.")
        return v


# --------------------------------------------------------------------------------------
# Build reproducibility (§27 version drift, §28 build metadata)
# --------------------------------------------------------------------------------------

class BuildMetadata(BaseModel):
    """Reproducibility record written next to a normalized build (§28).

    Generated and git-ignored (``data/build_metadata.json``). Records exactly which
    manifest, source fingerprints and pipeline code produced a normalized layer so a
    build is attributable to specific source versions (§27) and can be reproduced.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    canonical_schema_version: int = CANONICAL_SCHEMA_VERSION
    manifest_version: int | None = None
    pipeline_version: str | None = Field(
        default=None, description="Loader/pipeline version or code identifier."
    )
    git_commit: str | None = None
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_versions: dict[str, str] = Field(
        default_factory=dict, description="source_id -> exact source version consumed."
    )
    source_checksums: list[SourceFingerprint] = Field(default_factory=list)
    record_counts: dict[str, int] = Field(
        default_factory=dict, description="output name -> row count."
    )
    normalized_dir: str = "data/normalized"

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)


# --------------------------------------------------------------------------------------
# Serialization helpers — JSONL always; Parquet is opt-in (§9/§19)
# --------------------------------------------------------------------------------------

class ParquetUnavailableError(RuntimeError):
    """Raised when a Parquet helper is used without the optional pyarrow dependency."""


def write_jsonl(records: Iterable[BaseModel], path: str | Path) -> int:
    """Write pydantic records as JSON Lines (always available). Returns the row count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(rec.model_dump_json())
            fh.write("\n")
            n += 1
    return n


def read_jsonl(path: str | Path, model: type[BaseModel]) -> list[BaseModel]:
    """Read a JSON Lines file back into ``model`` instances."""
    out: list[BaseModel] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(model.model_validate_json(line))
    return out


def _require_pyarrow():
    try:
        import pyarrow as pa  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise ParquetUnavailableError(
            "Parquet support needs the optional knowledge-build dependency. Install it "
            'with:  pip install -e ".[knowledge]"  (or use the JSONL helpers instead).'
        ) from exc
    return pa, pq


def write_parquet(records: Sequence[BaseModel], path: str | Path) -> int:
    """Write pydantic records to a Parquet file (canonical normalized format).

    Lazy-imports pyarrow so the runtime never depends on it. Nested models are stored as
    JSON strings to keep a stable, portable columnar schema. Returns the row count.
    """
    pa, pq = _require_pyarrow()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_flatten_for_parquet(r.model_dump(mode="json")) for r in records]
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, str(path))
    return len(rows)


def read_parquet(path: str | Path, model: type[BaseModel]) -> list[BaseModel]:
    """Read a Parquet file written by :func:`write_parquet` back into ``model``."""
    _, pq = _require_pyarrow()
    table = pq.read_table(str(path))
    return [model.model_validate(_unflatten_from_parquet(row)) for row in table.to_pylist()]


def _flatten_for_parquet(d: dict[str, Any]) -> dict[str, Any]:
    """Encode nested dict/list fields as JSON strings for a stable columnar schema."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        out[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
    return out


def _unflatten_from_parquet(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str) and v[:1] in ("{", "["):
            try:
                out[k] = json.loads(v)
                continue
            except (ValueError, TypeError):
                pass
        out[k] = v
    return out


# ======================================================================================
# Phase 7A.1 — specialized records (compensation / labour market / credentials /
# crosswalk), source-quality category, requirement level, and the canonical-id registry.
# ======================================================================================

class SourceQualityCategory(str, Enum):
    """Deterministic source category (a provenance kind — NOT a numeric trust score) (§28)."""

    OFFICIAL_TAXONOMY = "official_taxonomy"          # O*NET, ESCO, ISCO, KldB
    OFFICIAL_STATISTICS = "official_statistics"      # Destatis, BLS OEWS, ONS, Eurostat
    OFFICIAL_REGULATORY = "official_regulatory"      # regulators / competent authorities
    OFFICIAL_LABOUR_MARKET = "official_labour_market"  # Cedefop, BA, EURES
    AUTHORIZED_MARKET_API = "authorized_market_api"  # Adzuna (advertised market)
    COMMERCIAL_ESTIMATE = "commercial_estimate"      # commercial salary estimators
    CURATED_INTERNAL = "curated_internal"            # Ask4Mo-authored


class RequirementLevel(str, Enum):
    """Task/qualification requirement (e.g. BA Anforderungsniveau) — a DIFFERENT dimension
    from :class:`Seniority` (§23). A helper role can still be 'senior'; do not map 1:1."""

    HELPER = "helper"          # Helfer / angelernt
    SKILLED = "skilled"        # Fachkraft
    SPECIALIST = "specialist"  # Spezialist
    EXPERT = "expert"          # Experte
    UNKNOWN = "unknown"


class CompensationStatistic(str, Enum):
    MEAN = "mean"
    MEDIAN = "median"
    P10 = "p10"
    P25 = "p25"
    P50 = "p50"
    P75 = "p75"
    P90 = "p90"
    MIN = "min"
    MAX = "max"


class PayPeriod(str, Enum):
    HOUR = "hour"
    WEEK = "week"    # e.g. ONS ASHE weekly pay — kept native, never silently annualised (§17)
    MONTH = "month"
    YEAR = "year"


class GrossNet(str, Enum):
    GROSS = "gross"
    NET = "net"
    UNKNOWN = "unknown"


class CompensationType(str, Enum):
    """The semantic KIND of pay evidence — never collapse these into a generic 'salary' (§15)."""

    OBSERVED_EARNINGS = "observed_earnings"      # official statistics (Destatis/BLS/ONS/Eurostat/BA)
    ADVERTISED_SALARY = "advertised_salary"      # job-ad salaries (Adzuna)
    MODELED_ESTIMATE = "modeled_estimate"        # a model/estimator output
    BASE_SALARY = "base_salary"
    TOTAL_CASH = "total_cash"
    TOTAL_COMPENSATION = "total_compensation"


class EmploymentBasis(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    ALL = "all"
    UNKNOWN = "unknown"


class CompensationRecord(BaseModel):
    """First-class compensation evidence (§16). NOT forced into KnowledgeFact so its
    statistic / period / gross-net / observed-vs-advertised semantics stay explicit and
    can be validated (§17)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    compensation_id: str = Field(min_length=1)

    occupation_id: str | None = None
    source_occupation_id: str | None = None
    occupation_code: str | None = None
    classification: ClassificationScheme | None = None

    country: str | None = None
    region: str | None = None
    city: str | None = None
    geography_type: GeographyType | None = None
    geography_code: str | None = None

    industry: str | None = None
    requirement_level: RequirementLevel | None = None
    seniority: Seniority | None = None

    currency: str | None = Field(default=None, description="ISO-4217, e.g. EUR/USD/GBP.")
    amount: float | None = None
    statistic: CompensationStatistic | None = None
    pay_period: PayPeriod | None = None
    gross_net: GrossNet = GrossNet.UNKNOWN
    compensation_type: CompensationType
    employment_basis: EmploymentBasis = EmploymentBasis.UNKNOWN

    effective_year: int | None = Field(default=None, ge=1900, le=2100)
    effective_period: str | None = None

    sample_size: int | None = None
    sample_size_known: bool = False
    suppressed: bool = False
    top_coded: bool = False
    estimated: bool = False

    source: str = Field(min_length=1)
    source_version: str | None = None
    source_record_id: str
    source_url: str | None = None
    source_quality: SourceQualityCategory | None = None
    retrieved_at: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("country", "currency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("occupation_id")
    @classmethod
    def _canon(cls, v: str | None) -> str | None:
        if v and not v.startswith("ask4mo:occ:"):
            raise ValueError("occupation_id must be an ask4mo:occ:<hash> canonical id.")
        return v


class MetricType(str, Enum):
    EMPLOYMENT = "employment"
    VACANCIES = "vacancies"
    UNEMPLOYMENT = "unemployment"
    GROWTH_RATE = "growth_rate"
    REPLACEMENT_DEMAND = "replacement_demand"
    JOB_OPENINGS = "job_openings"
    SHORTAGE_INDICATOR = "shortage_indicator"
    JOB_DENSITY = "job_density"
    CURRENT_POSTINGS = "current_postings"


class LabourMarketRecord(BaseModel):
    """Labour-market metric evidence (§18) — employment / vacancies / shortage / forecast."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    labour_market_id: str = Field(min_length=1)

    occupation_id: str | None = None
    source_occupation_id: str | None = None
    classification: ClassificationScheme | None = None

    country: str | None = None
    region: str | None = None
    geography_type: GeographyType | None = None
    geography_code: str | None = None
    industry: str | None = None

    metric_type: MetricType
    value: float | None = None
    unit: str | None = None

    effective_period: str | None = None
    forecast_period: str | None = None

    source: str = Field(min_length=1)
    source_version: str | None = None
    source_record_id: str
    source_url: str | None = None
    source_quality: SourceQualityCategory | None = None
    retrieved_at: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("country")
    @classmethod
    def _upper_c(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("occupation_id")
    @classmethod
    def _canon(cls, v: str | None) -> str | None:
        if v and not v.startswith("ask4mo:occ:"):
            raise ValueError("occupation_id must be an ask4mo:occ:<hash> canonical id.")
        return v


class CredentialType(str, Enum):
    LICENCE = "licence"
    CERTIFICATION = "certification"
    QUALIFICATION = "qualification"
    REGISTRATION = "registration"
    ACCREDITATION = "accreditation"
    UNKNOWN = "unknown"


class CredentialRecord(BaseModel):
    """Credential / regulated-profession evidence (§19). No scraping — schema only here."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    credential_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    credential_type: CredentialType = CredentialType.UNKNOWN

    occupation_id: str | None = None
    source_occupation_id: str | None = None

    country: str | None = None
    region: str | None = None

    required: bool = False
    recommended: bool = False
    regulated_profession: bool = False
    qualification_level: str | None = None

    issuing_body: str | None = None
    competent_authority: str | None = None

    source: str = Field(min_length=1)
    source_version: str | None = None
    source_record_id: str
    source_url: str | None = None
    source_quality: SourceQualityCategory | None = None
    effective_date: date | None = None
    retrieved_at: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("country")
    @classmethod
    def _upper_c(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class MappingType(str, Enum):
    EXACT = "exact"
    BROADER = "broader"
    NARROWER = "narrower"
    RELATED = "related"
    PARTIAL = "partial"


class MappingStrength(str, Enum):
    OFFICIAL = "official"       # published crosswalk from an authority
    DERIVED = "derived"         # deterministic transform
    CURATED = "curated"         # Ask4Mo-authored


class OccupationCrosswalk(BaseModel):
    """A mapping between two occupation identities/classifications (§20).

    IMPORTANT: a broad taxonomy relationship (e.g. same ISCO group) is ``broader`` /
    ``related`` — NOT ``exact``. Crosswalks describe relationships; they must not silently
    collapse two occupations into one.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    crosswalk_id: str = Field(min_length=1)

    source_occupation_id: str
    target_occupation_id: str
    source_classification: ClassificationScheme
    target_classification: ClassificationScheme
    source_code: str
    target_code: str

    mapping_type: MappingType = MappingType.RELATED
    mapping_strength: MappingStrength = MappingStrength.OFFICIAL
    official_mapping: bool = True

    source: str = Field(min_length=1)
    source_version: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OccupationRelationship(BaseModel):
    """A same-source occupation→occupation relationship (O*NET related, ISCO/KldB parent,
    OOH similar). Distinct from :class:`OccupationCrosswalk` (which links *classification
    schemes*); this links two occupations within one source's own hierarchy/graph. Preserved
    so the runtime transition/related-role lane keeps its evidence (Phase 7C)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    relationship_id: str = Field(min_length=1)
    occupation_id: str
    source_occupation_id: str = Field(min_length=1)
    related_code: str = Field(min_length=1)
    relation_type: str = "related"  # related | parent | similar (source-native)
    source: str = Field(min_length=1)
    source_version: str | None = None
    source_record_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occupation_id")
    @classmethod
    def _canon(cls, v: str) -> str:
        if not v.startswith("ask4mo:occ:"):
            raise ValueError("occupation_id must be an ask4mo:occ:<hash> canonical id.")
        return v


class CanonicalIdRegistry:
    """Persistent source-identifier → canonical Ask4Mo occupation-id map (§21).

    Guarantees canonical-id STABILITY: once an occupation has a canonical id, adding a
    richer classification later (e.g. an ESCO URI on top of an ISCO code) must NOT
    regenerate the id. The registry remembers every classification key that resolves to a
    given canonical id, so a later lookup by ANY of the occupation's keys returns the same
    id — even though :func:`canonical_occupation_id` alone would derive a different id from
    the higher-precedence key.
    """

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        # key ("scheme:value" / "native:src:id") -> canonical id
        self._map: dict[str, str] = dict(mapping or {})

    @staticmethod
    def _keys(**ids: str | None) -> list[str]:
        out: list[str] = []
        if ids.get("esco_uri"):
            out.append(f"{ClassificationScheme.ESCO.value}:{ids['esco_uri'].strip()}")
        if ids.get("onet_soc_code"):
            out.append(f"{ClassificationScheme.ONET_SOC.value}:{ids['onet_soc_code'].strip().lower()}")
        if ids.get("isco_code"):
            out.append(f"{ClassificationScheme.ISCO.value}:{str(ids['isco_code']).strip()}")
        if ids.get("soc_code"):
            out.append(f"{ClassificationScheme.SOC.value}:{str(ids['soc_code']).strip()}")
        if ids.get("kldb_code"):
            out.append(f"{ClassificationScheme.KLDB.value}:{str(ids['kldb_code']).strip()}")
        if ids.get("source") and ids.get("source_occupation_id"):
            out.append(f"native:{ids['source'].strip()}:{ids['source_occupation_id'].strip()}")
        return out

    def resolve_or_assign(self, **ids: str | None) -> str:
        """Return the stable canonical id for this occupation, assigning one on first sight.

        If any of the supplied identifiers is already known, its existing canonical id is
        returned and every new identifier is bound to it (enrichment). Otherwise a new id
        is derived (by the fixed precedence in :func:`canonical_occupation_id`) and all
        identifiers are registered to it.
        """
        keys = self._keys(**ids)
        if not keys:
            raise ValueError("resolve_or_assign needs at least one occupation identifier.")
        existing = next((self._map[k] for k in keys if k in self._map), None)
        canonical = existing or canonical_occupation_id(**ids)
        for k in keys:
            self._map.setdefault(k, canonical)
        return canonical

    def get(self, **ids: str | None) -> str | None:
        return next((self._map[k] for k in self._keys(**ids) if k in self._map), None)

    def as_dict(self) -> dict[str, str]:
        return dict(self._map)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"version": 1, "map": self._map}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CanonicalIdRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(mapping=data.get("map", {}))


__all__ += [
    "SourceQualityCategory",
    "RequirementLevel",
    "CompensationStatistic",
    "PayPeriod",
    "GrossNet",
    "CompensationType",
    "EmploymentBasis",
    "CompensationRecord",
    "MetricType",
    "LabourMarketRecord",
    "CredentialType",
    "CredentialRecord",
    "MappingType",
    "MappingStrength",
    "OccupationCrosswalk",
    "OccupationRelationship",
    "CanonicalIdRegistry",
]
