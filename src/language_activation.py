"""Language activation control (06H, REQ-LANG-11/13/14, OD-LANG-03/04): fail-closed enforcement of LG-01..LG-14.

A locale is OFFERED to real users, and ACCEPTED for new Candidate activity, only when the committed, reviewed readiness record
(``docs/production/execution/language_readiness.json``) holds a COMPLETE, APPROVED qualification for it:

  * all fourteen gates LG-01..LG-14 are present exactly once and every one is ``PASS``;
  * every PASS carries an ``evidence`` reference, a NAMED human ``approver``, an ``approved_on`` date (not in the future) and a
    ``release_sha``; an optional ``approved_until`` date bounds the approval;
  * the locale record carries the ``release_sha`` it is approved for, and every gate's ``release_sha`` equals it (a gate approved
    at another SHA is STALE) and no ``approved_until`` has passed;
  * the two claim flags (``production_qualified`` and ``offered_to_real_users``) agree with the derived result. They are claims,
    never inputs: editing a status string or a flag alone cannot enable a language.

Modes (server decision from ``API_ENV``, never a request field, never an Admin or environment toggle for the record itself):
  * ``enforced``  - production, staging and any UNKNOWN environment value: only qualified locales are offered and accepted. When
    none qualifies the offered set is EMPTY and every NEW language-bearing activity is refused (``language_not_activated``);
    English is not an implicit exception.
  * ``labelled``  - development and test: the seven ACTIVE candidate locales stay selectable and are visibly labelled UNQUALIFIED
    unless the record qualifies them.

An unreadable, malformed, duplicated-key or missing record fails closed (nothing qualifies). Russian (LG-14) is never activatable:
only members of ``ACTIVE_CANDIDATE_LOCALES`` can be offered, and a record for any other locale makes the file malformed.

This module reads no database and makes no network or provider call. It never turns an engineering translation into an approval.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.locales import ACTIVE_CANDIDATE_LOCALES

GATES: tuple[str, ...] = tuple(f"LG-{i:02d}" for i in range(1, 15))
STATES: frozenset[str] = frozenset({"NOT STARTED", "NOT RUN", "ENGINEERING DRAFT", "PASS"})
ERROR_CODE = "language_not_activated"
ERROR_MESSAGE = "This language is not yet available. Please choose another language or try again later."

MODE_ENFORCED = "enforced"
MODE_LABELLED = "labelled"
_LABELLED_ENVS = frozenset({"development", "dev", "local", "test", "testing"})

READINESS_PATH = Path(__file__).resolve().parent.parent / "docs" / "production" / "execution" / "language_readiness.json"

_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_PLACEHOLDER_WORDS = frozenset({"tbd", "todo", "n/a", "na", "none", "unknown", "unnamed", "pending", "anonymous", "-", "?", "reviewer", "approver", "native reviewer", "counsel"})
# Automation and engineering authorship is never a human approval (never convert an engineering translation into an approval).
_NOT_A_HUMAN = re.compile(r"\b(claude|chatgpt|gpt|llm|bot|automation|automated|github[- ]actions|system|script|engineering|machine)\b", re.I)


class ReadinessFormatError(ValueError):
    """The readiness file is not usable (unreadable, not JSON, duplicate keys, wrong shape). Callers fail closed."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ReadinessFormatError(f"duplicate key {key!r}")
        out[key] = value
    return out


def parse_readiness_text(text: str) -> dict[str, Any]:
    """Parse the record text, rejecting duplicate keys (a duplicated gate or locale would silently keep the last value)."""
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates)
    except ReadinessFormatError:
        raise
    except (ValueError, RecursionError) as exc:  # noqa: BLE001 - never echo the content
        raise ReadinessFormatError("readiness record is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ReadinessFormatError("readiness record is not an object")
    return data


def _today(today: date | None) -> date:
    return today or datetime.now(timezone.utc).date()


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def named_human(value: Any) -> bool:
    """A real, named person: not empty, not a placeholder, not an automation or engineering label."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    if len(v) < 3 or not re.search(r"[^\W\d_]", v):
        return False
    if v.lower() in _PLACEHOLDER_WORDS or _NOT_A_HUMAN.search(v):
        return False
    return True


@dataclass(frozen=True)
class LocaleStatus:
    code: str
    gates_pass: int
    qualified: bool
    problems: tuple[str, ...] = ()

    @property
    def state(self) -> str:
        return "QUALIFIED" if self.qualified else ("INCOMPLETE" if self.gates_pass else "UNQUALIFIED")


def validate_locale_record(code: str, rec: Any, *, today: date | None = None) -> LocaleStatus:
    """Validate ONE locale's qualification record. ``qualified`` is True only when there are no problems at all."""
    now = _today(today)
    problems: list[str] = []
    if not isinstance(rec, dict):
        return LocaleStatus(code, 0, False, ("record is not an object",))
    gates = rec.get("gates")
    if not isinstance(gates, dict):
        return LocaleStatus(code, 0, False, ("gates is not an object",))
    unknown = [g for g in gates if g not in GATES]
    if unknown:
        problems.append(f"unknown gate(s): {', '.join(sorted(map(str, unknown)))}")
    missing = [g for g in GATES if g not in gates]
    if missing:
        problems.append(f"missing gate(s): {', '.join(missing)}")
    if len(gates) != len(GATES):
        problems.append(f"gate count {len(gates)} is not {len(GATES)}")
    locale_sha = rec.get("release_sha")
    if not (isinstance(locale_sha, str) and _SHA.fullmatch(locale_sha)):
        problems.append("locale release_sha missing or malformed")
        locale_sha = None
    passed = 0
    for gate in GATES:
        e = gates.get(gate)
        if not isinstance(e, dict):
            continue
        if e.get("state") not in STATES:
            problems.append(f"{gate}: invalid state")
            continue
        if e["state"] != "PASS":
            problems.append(f"{gate}: state is {e['state']}")
            continue
        passed += 1
        ev = e.get("evidence")
        if not (isinstance(ev, str) and len(ev.strip()) >= 8 and ev.strip().lower() not in _PLACEHOLDER_WORDS):
            problems.append(f"{gate}: PASS without an evidence reference")
        if not named_human(e.get("approver")):
            problems.append(f"{gate}: PASS without a named human approver")
        approved_on = _iso_date(e.get("approved_on"))
        if approved_on is None:
            problems.append(f"{gate}: PASS without a valid approval date")
        elif approved_on > now:
            problems.append(f"{gate}: approval date is in the future")
        sha = e.get("release_sha")
        if not (isinstance(sha, str) and _SHA.fullmatch(sha)):
            problems.append(f"{gate}: PASS without a release SHA")
        elif locale_sha is not None and sha != locale_sha:
            problems.append(f"{gate}: stale (approved at a different release SHA)")
        if "approved_until" in e and e["approved_until"] is not None:
            until = _iso_date(e["approved_until"])
            if until is None:
                problems.append(f"{gate}: approved_until is not a valid date")
            elif until < now:
                problems.append(f"{gate}: stale (approved_until has passed)")
    qualified = not problems
    # The claim flags are claims, not inputs: they must agree with the derived result in both directions.
    for flag in ("production_qualified", "offered_to_real_users"):
        if rec.get(flag) is not qualified:
            problems.append(f"{flag} claim disagrees with the validated record")
    return LocaleStatus(code, passed, qualified and not problems, tuple(problems))


@dataclass(frozen=True)
class Activation:
    """The resolved, immutable activation decision for one process/request."""

    mode: str
    offered: tuple[str, ...]
    qualified: tuple[str, ...]
    locales: dict[str, LocaleStatus] = field(default_factory=dict)
    file_error: str | None = None

    @property
    def enforced(self) -> bool:
        return self.mode == MODE_ENFORCED

    @property
    def unqualified_offered(self) -> tuple[str, ...]:
        """Locales selectable but visibly UNQUALIFIED (labelled mode only; always empty when enforced)."""
        return tuple(c for c in self.offered if c not in self.qualified)

    def accepts(self, code: object) -> bool:
        return isinstance(code, str) and code in self.offered

    @property
    def none_available(self) -> bool:
        return not self.offered


def resolve(data: dict[str, Any] | None, mode: str, *, today: date | None = None, file_error: str | None = None) -> Activation:
    """PURE resolver. ``data`` None or malformed means nothing qualifies (fail closed)."""
    locales: dict[str, LocaleStatus] = {}
    error = file_error
    qualified: tuple[str, ...] = ()
    if data is not None and error is None:
        langs = data.get("languages")
        if not isinstance(langs, dict):
            error = "languages is not an object"
        else:
            stray = [c for c in langs if c not in ACTIVE_CANDIDATE_LOCALES]
            if stray:
                # A record for any non-active locale (Russian: LG-14) makes the file untrustworthy: fail closed for everything.
                error = f"record for a non-active locale: {', '.join(sorted(map(str, stray)))}"
    if error is None and data is not None:
        for code in ACTIVE_CANDIDATE_LOCALES:
            locales[code] = validate_locale_record(code, data["languages"].get(code), today=today)
        qualified = tuple(c for c in ACTIVE_CANDIDATE_LOCALES if locales[c].qualified)
    else:
        locales = {c: LocaleStatus(c, 0, False, ("readiness record unusable",)) for c in ACTIVE_CANDIDATE_LOCALES}
    offered = qualified if mode == MODE_ENFORCED else tuple(ACTIVE_CANDIDATE_LOCALES)
    return Activation(mode=mode, offered=offered, qualified=qualified, locales=locales, file_error=error)


def activation_mode(environ: dict[str, str] | None = None) -> str:
    env = (((environ if environ is not None else os.environ).get("API_ENV")) or "development").strip().lower()
    return MODE_LABELLED if env in _LABELLED_ENVS else MODE_ENFORCED  # staging, production and any unknown value enforce


def load_committed(path: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Read the committed record. Returns (data, None) or (None, safe error). Never raises."""
    try:
        text = (path or READINESS_PATH).read_text(encoding="utf-8")
    except OSError:
        return None, "readiness record unreadable"
    try:
        return parse_readiness_text(text), None
    except ReadinessFormatError as exc:
        return None, str(exc)


# ---- runtime accessor and the test-only seam ----------------------------------------------------------------------------------------------------------
_cache: dict[str, Any] = {}
_test_records: dict[str, Any] | None = None


def current(*, today: date | None = None) -> Activation:
    """The activation decision for this process. The record is read from the committed file (cached); the mode from API_ENV."""
    mode = activation_mode()
    if _test_records is not None:
        return resolve(_test_records, mode, today=today)
    if "data" not in _cache:
        data, err = load_committed()
        _cache["data"], _cache["error"] = data, err
    return resolve(_cache["data"], mode, today=today, file_error=_cache["error"])


def _assert_test_harness() -> None:
    if "pytest" not in sys.modules or not os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("The synthetic readiness seam is available only inside the test harness.")


def install_test_records(records: dict[str, Any] | None) -> None:
    """TEST-ONLY seam: replace the committed record with a synthetic one (same validator, same resolver).

    Refuses outside a running pytest session, so it is unreachable in any production configuration. Production code never calls it
    (a static test asserts that). ``None`` removes the override.
    """
    global _test_records
    _assert_test_harness()
    _test_records = records
    _cache.clear()


def reset_for_tests() -> None:
    global _test_records
    _test_records = None
    _cache.clear()


def require_locale_activated(code: str | None) -> str:
    """Entry-point guard for NEW Candidate activity. ``code`` None means the default language, which is NOT exempt."""
    from src.locales import DEFAULT_ACTIVE_LOCALE

    chosen = code or DEFAULT_ACTIVE_LOCALE
    if not current().accepts(chosen):
        from src.api.coded_errors import CodedHTTPException

        raise CodedHTTPException(422, ERROR_CODE, ERROR_MESSAGE)
    return chosen


def public_summary(act: Activation | None = None) -> dict[str, Any]:
    """Safe, public projection (locale codes and mode only; no gate detail, no problems text)."""
    a = act or current()
    return {
        "mode": a.mode,
        "offered_locales": list(a.offered),
        "qualified_locales": list(a.qualified),
        "unqualified_locales": list(a.unqualified_offered),
        "none_available": a.none_available,
    }


def admin_summary(act: Activation | None = None) -> dict[str, Any]:
    """Counts and states only (no evidence text, no approver names, no SHAs, no secrets)."""
    a = act or current()
    return {
        **public_summary(a),
        "record_usable": a.file_error is None,
        "locales": {c: {"gates_passed": s.gates_pass, "gates_total": len(GATES), "state": s.state, "open_problems": len(s.problems)} for c, s in a.locales.items()},
    }
