"""Market source approval (02D, PG-05, OD-LANG-02, OD-US-CONTENT): fail-closed enforcement of source qualification.

A knowledge source may reach a Candidate for a market only when the committed, reviewed register
(``docs/production/execution/source_approval_register.json``) holds a COMPLETE, APPROVED record for that exact ``(source_id, market)`` pair.
The register is the single source of truth: it is a committed file (like ``language_readiness.json``), never a toggle, never an environment
variable, never an Admin control. NO source is approved today: the register ships EMPTY and nothing in this module can approve anything.

A record ENABLES ``(source, market)`` only when every field below is present and valid:

  * ``source_id`` (an existing manifest source or an ``governed:<id>`` Admin-governed source) and ``market`` (one of :data:`MARKETS`);
  * ``licence_class`` (one of the Admin knowledge licence classes that may be activated, never ``unclear`` or ``restricted``) and a
    ``licence_terms_reference`` (where the exact licence terms were read);
  * ``rights_holder`` (the named rights holder) and ``authority_tier`` (1 official, 2 framework, 3 industry; must equal the manifest tier);
  * ``coverage_statement`` and ``features`` (which :data:`FEATURES` the source may serve for that market);
  * ``approver`` (a NAMED human: never a placeholder or an automation label), ``approved_on`` (not in the future), ``evidence_reference``
    and ``release_sha`` (the release the approval was given for);
  * ``staleness_rule`` ``{"valid_until": "YYYY-MM-DD"}`` (not passed, and not later than :data:`MAX_APPROVAL_DAYS` after ``approved_on``);
  * the claim ``enabled`` agrees with the derived result. The claim is never an input: editing it alone cannot enable a source.

A missing, partial, duplicated, forged, malformed or stale record fails closed. An unreadable or malformed file makes the whole register
empty. Duplicate JSON keys and duplicate ``(source_id, market)`` pairs make the file malformed.

Modes (server decision from ``API_ENV``, never a request field): ``enforced`` (production, staging and any UNKNOWN value) refuses every
unapproved source; ``labelled`` (development, test) keeps the source reachable but labels it UNQUALIFIED so developers see the same finding.

OD-US-CONTENT: US-published content for a non-US market is refused by :func:`decide` regardless of any record unless the code constant
:data:`US_GENERAL_INFORMATION_DECIDED` is True (it is False: the owner has not decided, so the content is unclassified), and then it is
always labelled non-EU general information. The market is the Candidate's market (selected geography or the country the question names);
it is never derived from the interface or conversation language.

This module reads no database and makes no network or provider call.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from src.knowledge_admin.policy import ACTIVATABLE_LICENCES, LICENCE_CLASSES

REGISTER_PATH = Path(__file__).resolve().parent.parent / "docs" / "production" / "execution" / "source_approval_register.json"

MARKETS: tuple[str, ...] = ("IE", "DE", "ES", "IT", "PT", "FR", "NL", "UK", "US", "EU")
# The 02E beta-scope features (same vocabulary as src/copilot/evaluation/beta_scope_coverage.py on 02E, kept in sync by a test when both exist).
FEATURES: tuple[str, ...] = ("role_definition", "compensation", "labour_outlook", "entry_education", "licence", "certification")
AUTHORITY_TIERS = (1, 2, 3)
MAX_APPROVAL_DAYS = 366
GOVERNED_PREFIX = "governed:"

# OD-US-CONTENT. A code constant, not a setting: the owner has not decided, so US-published content stays unclassified and OFF.
US_GENERAL_INFORMATION_DECIDED = False
US_GENERAL_INFORMATION_LABEL = "General information from a US source, not specific to your market"

MODE_ENFORCED = "enforced"
MODE_LABELLED = "labelled"
_LABELLED_ENVS = frozenset({"development", "dev", "local", "test", "testing"})

_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_SOURCE_ID = re.compile(r"^(governed:)?[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")
_PLACEHOLDER_WORDS = frozenset({"tbd", "todo", "n/a", "na", "none", "unknown", "unnamed", "pending", "anonymous", "-", "?", "reviewer", "approver",
                                "counsel", "legal", "owner", "licensing reviewer"})
_NOT_A_HUMAN = re.compile(r"\b(claude|chatgpt|gpt|llm|bot|automation|automated|github[- ]actions|system|script|engineering|machine)\b", re.I)
_REQUIRED_FIELDS = ("source_id", "market", "licence_class", "licence_terms_reference", "rights_holder", "authority_tier", "coverage_statement",
                    "features", "approver", "approved_on", "evidence_reference", "release_sha", "staleness_rule", "enabled")
_MARKET_ALIASES = {"GB": "UK", "UK": "UK"}


class RegisterFormatError(ValueError):
    """The register file is not usable (unreadable, not JSON, duplicate keys, wrong shape). Callers fail closed."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise RegisterFormatError(f"duplicate key {key!r}")
        out[key] = value
    return out


def parse_register_text(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates)
    except RegisterFormatError:
        raise
    except (ValueError, RecursionError) as exc:  # noqa: BLE001 - never echo the content
        raise RegisterFormatError("approval register is not valid JSON") from exc
    if not isinstance(data, dict):
        raise RegisterFormatError("approval register is not an object")
    return data


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _today(today: date | None) -> date:
    return today or datetime.now(timezone.utc).date()


def named_human(value: Any) -> bool:
    """A real, named person: not empty, not a placeholder, not an automation or engineering label."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    if len(v) < 3 or not re.search(r"[^\W\d_]", v):
        return False
    return not (v.lower() in _PLACEHOLDER_WORDS or _NOT_A_HUMAN.search(v))


def _text(value: Any, minimum: int = 8) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum and value.strip().lower() not in _PLACEHOLDER_WORDS


def normalise_market(value: object) -> str | None:
    """Map a candidate geography or detected country code to a register market, or None when it is not one (global, other, unspecified)."""
    if not isinstance(value, str):
        return None
    code = _MARKET_ALIASES.get(value.strip().upper(), value.strip().upper())
    return code if code in MARKETS else None


def source_key(metadata: dict[str, Any] | None, source_id: str | None = None) -> str | None:
    """The register identity of a piece of evidence: ``governed:<id>`` for Admin-governed knowledge, the manifest source id otherwise, None if unknown."""
    meta = metadata or {}
    gov = meta.get("knowledge_source_id")
    if gov not in (None, ""):
        return f"{GOVERNED_PREFIX}{gov}"
    for raw in (meta.get("manifest_source_id"), source_id, meta.get("source_id")):
        if isinstance(raw, str) and raw.strip():
            return raw.strip().split(":", 1)[0]
    return None


@dataclass(frozen=True)
class RecordStatus:
    source_id: str
    market: str
    enabled: bool
    problems: tuple[str, ...] = ()


def validate_record(rec: Any, *, today: date | None = None, manifest_tiers: dict[str, int] | None = None) -> RecordStatus:
    """Validate ONE record. ``enabled`` is True only when there are no problems. ``manifest_tiers`` (source id to tier) adds the existence and tier checks."""
    now = _today(today)
    if not isinstance(rec, dict):
        return RecordStatus("?", "?", False, ("record is not an object",))
    problems: list[str] = []
    sid, market = rec.get("source_id"), rec.get("market")
    shown_sid = sid if isinstance(sid, str) and _SOURCE_ID.fullmatch(sid) else "?"
    shown_market = market if market in MARKETS else "?"
    unknown = [k for k in rec if k not in _REQUIRED_FIELDS and k not in ("approved_until", "notes")]
    if unknown:
        problems.append(f"unknown field(s): {', '.join(sorted(map(str, unknown)))}")
    missing = [f for f in _REQUIRED_FIELDS if f not in rec]
    if missing:
        problems.append(f"missing field(s): {', '.join(missing)}")
    if shown_sid == "?":
        problems.append("source_id missing or malformed")
    elif manifest_tiers is not None and not shown_sid.startswith(GOVERNED_PREFIX) and shown_sid not in manifest_tiers:
        problems.append("source_id does not reference an existing manifest source")
    if shown_market == "?":
        problems.append("market is not a known market")
    if rec.get("licence_class") not in LICENCE_CLASSES:
        problems.append("licence_class is not a known class")
    elif rec["licence_class"] not in ACTIVATABLE_LICENCES:
        problems.append(f"licence_class {rec['licence_class']} cannot be enabled")
    for f in ("licence_terms_reference", "rights_holder", "coverage_statement", "evidence_reference"):
        if f in rec and not _text(rec.get(f)):
            problems.append(f"{f} is empty or a placeholder")
    tier = rec.get("authority_tier")
    if "authority_tier" in rec:
        if isinstance(tier, bool) or tier not in AUTHORITY_TIERS:
            problems.append("authority_tier is not 1, 2 or 3")
        elif manifest_tiers is not None and shown_sid in manifest_tiers and manifest_tiers[shown_sid] != tier:
            problems.append("authority_tier disagrees with the manifest")
    feats = rec.get("features")
    if "features" in rec and not (isinstance(feats, list) and feats and len(set(feats)) == len(feats) and all(f in FEATURES for f in feats)):
        problems.append("features must be a non-empty list of known, distinct features")
    if "approver" in rec and not named_human(rec.get("approver")):
        problems.append("approver is not a named human")
    approved_on = _iso_date(rec.get("approved_on"))
    if "approved_on" in rec:
        if approved_on is None:
            problems.append("approved_on is not a valid date")
        elif approved_on > now:
            problems.append("approved_on is in the future")
    if "release_sha" in rec and not (isinstance(rec.get("release_sha"), str) and _SHA.fullmatch(rec["release_sha"])):
        problems.append("release_sha missing or malformed")
    rule = rec.get("staleness_rule")
    if "staleness_rule" in rec:
        until = _iso_date(rule.get("valid_until")) if isinstance(rule, dict) and set(rule) == {"valid_until"} else None
        if until is None:
            problems.append("staleness_rule must be exactly {valid_until: YYYY-MM-DD}")
        else:
            if until < now:
                problems.append("stale (valid_until has passed)")
            if approved_on is not None and until > approved_on + timedelta(days=MAX_APPROVAL_DAYS):
                problems.append(f"valid_until is more than {MAX_APPROVAL_DAYS} days after approved_on")
    if rec.get("approved_until") is not None and _iso_date(rec.get("approved_until")) is None:
        problems.append("approved_until is not a valid date")
    enabled = not problems
    if rec.get("enabled") is not enabled:     # the claim must agree in both directions; it is never an input
        problems.append("enabled claim disagrees with the validated record")
    return RecordStatus(shown_sid, shown_market, enabled and not problems, tuple(problems))


@dataclass(frozen=True)
class Register:
    """The resolved approval register. ``enabled`` holds the ``(source_id, market)`` pairs with a complete, valid record."""

    mode: str
    records: tuple[RecordStatus, ...] = ()
    features: dict[tuple[str, str], frozenset[str]] = field(default_factory=dict)
    file_error: str | None = None

    @property
    def enabled(self) -> frozenset[tuple[str, str]]:
        return frozenset((r.source_id, r.market) for r in self.records if r.enabled)

    @property
    def enforced(self) -> bool:
        return self.mode == MODE_ENFORCED

    @property
    def empty(self) -> bool:
        return not self.enabled

    def is_enabled(self, source: str | None, market: str | None) -> bool:
        return bool(source and market and (source, market) in self.enabled)


def resolve(data: dict[str, Any] | None, mode: str, *, today: date | None = None, file_error: str | None = None,
            manifest_tiers: dict[str, int] | None = None) -> Register:
    """PURE resolver. ``data`` None or malformed means nothing is enabled (fail closed)."""
    error = file_error
    recs: list[Any] = []
    if error is None and data is None:
        error = "approval register unusable"
    if error is None:
        raw = data.get("records")  # type: ignore[union-attr]
        if data.get("schema_version") != 1:  # type: ignore[union-attr]
            error = "unsupported schema_version"
        elif not isinstance(raw, list):
            error = "records is not a list"
        else:
            recs = raw
    if error is not None:
        return Register(mode=mode, file_error=error)
    statuses = [validate_record(r, today=today, manifest_tiers=manifest_tiers) for r in recs]
    pairs = [(s.source_id, s.market) for s in statuses if s.source_id != "?" and s.market != "?"]
    if len(pairs) != len(set(pairs)):
        return Register(mode=mode, file_error="duplicate (source_id, market) record")
    feats = {(s.source_id, s.market): frozenset(r["features"]) for s, r in zip(statuses, recs) if s.enabled}
    return Register(mode=mode, records=tuple(statuses), features=feats)


def approval_mode(environ: dict[str, str] | None = None) -> str:
    env = (((environ if environ is not None else os.environ).get("API_ENV")) or "development").strip().lower()
    return MODE_LABELLED if env in _LABELLED_ENVS else MODE_ENFORCED


def load_committed(path: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Read the committed register. Returns (data, None) or (None, safe error). Never raises."""
    try:
        text = (path or REGISTER_PATH).read_text(encoding="utf-8")
    except OSError:
        return None, "approval register unreadable"
    try:
        return parse_register_text(text), None
    except RegisterFormatError as exc:
        return None, str(exc)


def manifest_tiers() -> dict[str, int] | None:
    """Manifest source id to authority tier, or None when the manifest cannot be read (the existence check is then skipped, never granted)."""
    try:
        from src.copilot.knowledge import manifest as km

        return {e.source_id: e.authority_level for e in km.load_manifest()}
    except Exception:  # noqa: BLE001
        return None


# ---- runtime accessor and the test-only seam ----------------------------------------------------------------------------------------------------------
_cache: dict[str, Any] = {}
_synthetic_register: dict[str, Any] | None = None


def current(*, today: date | None = None) -> Register:
    mode = approval_mode()
    tiers = manifest_tiers()
    if _synthetic_register is not None:
        return resolve(_synthetic_register, mode, today=today, manifest_tiers=tiers)
    if "data" not in _cache:
        data, err = load_committed()
        _cache["data"], _cache["error"] = data, err
    return resolve(_cache["data"], mode, today=today, file_error=_cache["error"], manifest_tiers=tiers)


def install_synthetic_register(records: dict[str, Any] | None) -> None:
    """TEST-ONLY seam: replace the committed register with a synthetic one (same validator, same resolver). Refuses outside a running pytest session."""
    global _synthetic_register
    if "pytest" not in sys.modules or not os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("The synthetic approval seam is available only inside the test harness.")
    _synthetic_register = records
    _cache.clear()


def clear_synthetic_register() -> None:
    global _synthetic_register
    _synthetic_register = None
    _cache.clear()


# ---- the decision --------------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Decision:
    allowed: bool
    labelled_unqualified: bool = False   # dev only: allowed but shown as unqualified
    general_information: bool = False    # US content shown as non-EU general information (only if OD-US-CONTENT is decided)
    reason: str = ""


def decide(register: Register, source: str | None, market: str | None, *, source_country: str | None = None) -> Decision:
    """Fail-closed decision for one source and the Candidate's market. ``source_country`` is the publisher country from the manifest."""
    mkt = normalise_market(market)
    us_source = (source_country or "").upper() == "US"
    if us_source and mkt != "US" and not US_GENERAL_INFORMATION_DECIDED:
        # OD-US-CONTENT undecided: US-published content is unclassified and never reaches a non-US (or unknown) market, even with a record.
        return _refuse(register, "us_content_undecided")
    if register.is_enabled(source, mkt):
        return Decision(True, general_information=us_source and mkt != "US", reason="approved")
    reason = "no_market" if mkt is None else ("no_source" if not source else "not_approved")
    return _refuse(register, reason)


def _refuse(register: Register, reason: str) -> Decision:
    return Decision(False, reason=reason) if register.enforced else Decision(True, labelled_unqualified=True, reason=reason)


# ---- consistency check (licence register) -------------------------------------------------------------------------------------------------------------
def consistency_problems(register_data: dict[str, Any] | None, manifest_entries: Iterable[Any], *, today: date | None = None) -> list[str]:
    """Register and manifest consistency (02D). Empty list means consistent.

    * every manifest source carries a licence entry: a licence string, or the explicit ``licence_review_required`` flag (an unresolved,
      visible entry; never a silent gap);
    * a manifest source whose licence is unresolved (``licence_review_required``) or non-redistributable cannot have an enabled record unless
      the record's licence class was set by a reviewer (the validator already refuses ``unclear``/``restricted``) - reported as a warning-level problem
      only when the record claims a class while the manifest still says review is required, so the manifest must be updated in the same change;
    * every record references an existing manifest source or an ``governed:`` source, has a known market and a matching tier.
    """
    entries = list(manifest_entries)
    out: list[str] = []
    ids = [e.source_id for e in entries]
    if len(ids) != len(set(ids)):
        out.append("duplicate manifest source_id")
    for e in entries:
        if not ((e.licence or "").strip() or e.licence_review_required):
            out.append(f"{e.source_id}: no licence entry (neither a licence nor licence_review_required)")
    tiers = {e.source_id: e.authority_level for e in entries}
    by_id = {e.source_id: e for e in entries}
    reg = resolve(register_data, MODE_ENFORCED, today=today, manifest_tiers=tiers)
    if reg.file_error:
        out.append(f"register unusable: {reg.file_error}")
        return out
    for r in reg.records:
        for p in r.problems:
            out.append(f"{r.source_id}/{r.market}: {p}")
        if r.enabled and r.source_id in by_id and by_id[r.source_id].licence_review_required:
            out.append(f"{r.source_id}/{r.market}: enabled while the manifest still marks the licence review_required (update the manifest with the review outcome)")
    return out


# ---- adapter for the 02E beta-scope coverage reader ----------------------------------------------------------------------------------------------------
def beta_scope_view(reg: Register | None = None) -> dict[str, Any]:
    """The register in the shape 02E's ``evaluations/beta_scope_coverage/approval_register.json`` uses (enabled_features, approved_markets, qualified_sources).

    02E reads this single source through the adapter instead of keeping its own snapshot. Empty register, empty view.
    """
    r = reg or current()
    pairs = sorted(r.enabled)
    feats = sorted({f for p in pairs for f in r.features.get(p, ())})
    markets = sorted({m for _, m in pairs})
    return {"schema_version": 1, "enabled_features": feats, "approved_markets": markets,
            "qualified_sources": [{"source_id": s, "market": m} for s, m in pairs]}


def public_summary(reg: Register | None = None) -> dict[str, Any]:
    """Counts and mode only (no approver names, no evidence references, no SHAs)."""
    r = reg or current()
    return {"mode": r.mode, "enabled_pairs": len(r.enabled), "enabled_markets": sorted({m for _, m in r.enabled}),
            "register_usable": r.file_error is None, "none_enabled": r.empty}
