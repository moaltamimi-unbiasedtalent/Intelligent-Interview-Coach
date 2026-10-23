#!/usr/bin/env python
"""08A0 release evidence pipeline: a committed evidence ledger, a generated status view and a checker. OFFLINE by default.

    python scripts/production/release_evidence.py generate   rewrite the generated view and matrix inputs from the ledger (+ PACKAGE_STATUS, wave_matrix, the tracker)
    python scripts/production/release_evidence.py check      fail on an unevidenced or stale PASS, a language-gate rule violation, a tracker contradiction, a stale view, a failed reconciliation
    python scripts/production/release_evidence.py sync       add a NOT RUN / OPEN ledger entry for every MERGED package that has none (never a PASS)
    python scripts/production/release_evidence.py check --fetch   additionally compare the ledger with GitHub (public, UNAUTHENTICATED API; explicit opt-in; never run by default or in CI)

Sources of truth (nothing is duplicated here):
  * package state, PR number, merge and head SHA: ``execution_packages.PACKAGE_STATUS`` (read, cross-checked against the ledger);
  * the live-staging / human / gate descriptions: ``wave_matrix.LAYERS`` (read);
  * gate names, packages and state: ``docs/production/execution/RELEASE_READINESS_TRACKER.md`` (read, cross-checked against the ledger);
  * language-gate rules: ``src/language_activation.py`` (``validate_locale_record`` and ``named_human`` are CALLED, never re-implemented or loosened);
  * the ledger ``docs/production/execution/release_evidence_ledger.json`` holds what is NOT elsewhere: artefact links, PR numbers and merge SHAs, CI results, dates and who
    or what produced each piece of evidence.

Rules: NOTHING is ever marked PASS automatically (this tool never writes a positive state). A positive state (PASS, ACCEPTED, COMPLETE) needs an artefact link, an evidence
SHA, an evidence date and a producer that is a named human or CI. Engineering, CI, live staging, human qualification and gate acceptance stay separate (five layers,
WAVE3_EXECUTION_PLAN.md section 3). Staleness is deterministic (see ``is_stale``). Default path performs no network call; ``--fetch`` lazily imports urllib.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import language_activation as LA  # noqa: E402  (rules are reused, never copied)

EXEC = ROOT / "docs/production/execution"
LEDGER = EXEC / "release_evidence_ledger.json"
SCHEMA_FILE = EXEC / "release_evidence_ledger.schema.json"
TRACKER = EXEC / "RELEASE_READINESS_TRACKER.md"
READINESS = LA.READINESS_PATH
VIEW = EXEC / "RELEASE_EVIDENCE_VIEW.md"
MATRIX_INPUTS = EXEC / "release_evidence_matrix_inputs.json"
RECON = ROOT / "docs/production/PRODUCTION_ISSUE_RECONCILIATION.json"

SCHEMA_ID = "ask4mo.release_evidence.v1"
REPO = "moaltamimi-unbiasedtalent/Intelligent-Interview-Coach"
PG_GATES = tuple(f"PG-{i:02d}" for i in range(1, 16))
LG_GATES = tuple(LA.GATES)
GATE_STATES = ("NOT STARTED", "IN PROGRESS", "READY FOR REVIEW", "PASS", "FAIL", "BLOCKED")
CI_RESULTS = ("success", "failure", "not recorded", "not run")
# The three layers the ledger records beside engineering and CI (which are derived). First state of each tuple is the default; the LAST positive state needs evidence.
LAYER_STATES = {
    "live_staging": ("NOT RUN", "N/A", "FAIL", "PASS"),
    "human_qualification": ("OPEN", "NONE REQUIRED", "REJECTED", "COMPLETE"),
    "gate_acceptance": ("NOT ACCEPTED", "REJECTED", "ACCEPTED"),
}
POSITIVE = {"live_staging": "PASS", "human_qualification": "COMPLETE", "gate_acceptance": "ACCEPTED"}
LAYER_ORDER = ("live_staging", "human_qualification", "gate_acceptance")
PRODUCER_TYPES = ("human", "ci")
BINDINGS = ("date", "release_sha")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HTTPS = re.compile(r"^https://[^\s/]+/\S*$")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W = _load(ROOT / "scripts/production/wave_matrix.py", "wave_matrix")     # wave_matrix itself loads execution_packages as W.E
E = W.E


# ---------------------------------------------------------------------------------------------------------------- small helpers
def iso(value: Any) -> date | None:
    if not isinstance(value, str) or not _DATE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def sha_ok(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA.match(value))


def same_sha(a: str, b: str) -> bool:
    """Short and full SHAs name the same commit when one is a prefix of the other."""
    a, b = a.lower(), b.lower()
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def is_stale(evidence_date: date, valid_days: int, today: date) -> bool:
    """Deterministic staleness: evidence is valid through ``evidence_date + valid_days`` inclusive; the day after, it is stale. No clock other than ``today`` is read."""
    return today > evidence_date + timedelta(days=valid_days)


def link_ok(link: Any, root: Path = ROOT) -> bool:
    """An artefact link is an https URL or a repository-relative file path that exists. Placeholders are refused."""
    if not isinstance(link, str):
        return False
    v = link.strip()
    if not v or v.lower() in LA._PLACEHOLDER_WORDS:  # noqa: SLF001 - the shared placeholder list
        return False
    if _HTTPS.match(v):
        return True
    path = v.split("#", 1)[0]
    if path.startswith(("/", "..")) or "://" in path:
        return False
    return (root / path).is_file()


def links_in(text: Any, root: Path = ROOT) -> list[str]:
    """Language-gate evidence is a free string (the 06A format); the links it names are the whitespace/semicolon/comma separated tokens that are valid links."""
    if not isinstance(text, str):
        return []
    return [t for t in re.split(r"[;,\s]+", text) if t and link_ok(t, root)]


# ---------------------------------------------------------------------------------------------------------------- loading
def load_ledger(path: Path = LEDGER) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_ledger(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def tracker_gates(text: str | None = None) -> dict[str, dict]:
    """Parse the PG rows of RELEASE_READINESS_TRACKER.md section 1: id -> name, packages, state (the leading vocabulary word(s) of the State cell)."""
    text = TRACKER.read_text(encoding="utf-8") if text is None else text
    out: dict[str, dict] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"PG-\d\d", cells[0]):
            state = next((s for s in sorted(GATE_STATES, key=len, reverse=True) if cells[4].startswith(s)), cells[4])
            out[cells[0]] = {"name": cells[1], "packages": cells[2], "state": state, "state_text": cells[4], "evidence": cells[5] if len(cells) > 5 else ""}
    return out


LANG_NAMES = {"English": "en", "German": "de", "Spanish": "es", "Italian": "it", "Portuguese": "pt", "French": "fr", "Dutch": "nl"}


def tracker_language_counts(text: str | None = None) -> dict[str, int]:
    """Section 2 of the tracker: language code -> 'N of 14' gates approved."""
    text = TRACKER.read_text(encoding="utf-8") if text is None else text
    out: dict[str, int] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in LANG_NAMES:
            m = re.match(r"(\d+) of 14", cells[2])
            if m:
                out[LANG_NAMES[cells[0]]] = int(m.group(1))
    return out


def package_pr_facts(pid: str) -> dict | None:
    """What PACKAGE_STATUS records for a MERGED package: PR number, merge SHA, head SHA. None when the package is not merged."""
    st = E.PACKAGE_STATUS.get(pid)
    if not st or not st[0].startswith("MERGED"):
        return None
    pr = re.search(r"PR #(\d+)", st[0])
    merge = re.search(r"merge ([0-9a-f]{7,40})", st[0])
    return {"pr": int(pr.group(1)) if pr else None, "merge": merge.group(1) if merge else None, "head": st[2] or None, "branch": st[1]}


def merged_package_ids() -> list[str]:
    return [pid for pid in E.PACKAGE_STATUS if package_pr_facts(pid)]


def pr_url(n: int) -> str:
    return f"https://github.com/{REPO}/pull/{n}"


# ---------------------------------------------------------------------------------------------------------------- schema (hand-written, dependency free; SCHEMA_FILE documents the same shape)
def _is_str(v: Any, minlen: int = 1) -> bool:
    return isinstance(v, str) and len(v.strip()) >= minlen


def _evidence_entry_problems(where: str, e: Any) -> list[str]:
    if not isinstance(e, dict):
        return [f"{where}: evidence entry is not an object"]
    p: list[str] = []
    allowed = {"kind", "link", "sha", "date", "produced_by", "produced_by_type", "binding", "valid_days", "note"}
    for k in e:
        if k not in allowed:
            p.append(f"{where}: unknown evidence field {k!r}")
    for k in ("kind", "link", "sha", "date", "produced_by", "produced_by_type"):
        if k not in e:
            p.append(f"{where}: evidence field {k!r} missing")
    if "sha" in e and not sha_ok(e["sha"]):
        p.append(f"{where}: evidence sha malformed")
    if "date" in e and iso(e["date"]) is None:
        p.append(f"{where}: evidence date malformed")
    if "produced_by_type" in e and e["produced_by_type"] not in PRODUCER_TYPES:
        p.append(f"{where}: produced_by_type must be one of {list(PRODUCER_TYPES)}")
    if "binding" in e and e["binding"] not in BINDINGS:
        p.append(f"{where}: binding must be one of {list(BINDINGS)}")
    if "valid_days" in e and not (isinstance(e["valid_days"], int) and not isinstance(e["valid_days"], bool) and e["valid_days"] > 0):
        p.append(f"{where}: valid_days must be a positive integer")
    for k in ("kind", "link", "produced_by"):
        if k in e and not _is_str(e[k]):
            p.append(f"{where}: evidence {k} must be a non-empty string")
    return p


def schema_problems(doc: Any) -> list[str]:
    """Structural validation of the ledger. Returns problems (empty = the shape is valid). Semantic rules live in ``check_ledger``."""
    p: list[str] = []
    if not isinstance(doc, dict):
        return ["ledger is not an object"]
    for k in ("schema", "as_of", "main_sha", "policy", "pull_requests", "packages", "gates", "language_gates"):
        if k not in doc:
            p.append(f"missing top-level field {k!r}")
    for k in doc:
        if k not in {"schema", "note", "as_of", "main_sha", "policy", "pull_requests", "packages", "gates", "language_gates"}:
            p.append(f"unknown top-level field {k!r}")
    if p:
        return p
    if doc["schema"] != SCHEMA_ID:
        p.append(f"schema must be {SCHEMA_ID!r}")
    if iso(doc["as_of"]) is None:
        p.append("as_of is not a valid date")
    if not sha_ok(doc["main_sha"]):
        p.append("main_sha malformed")
    pol = doc["policy"]
    if not isinstance(pol, dict) or set(pol) != {"gate_evidence_valid_days", "language_approval_valid_days", "layer_evidence_valid_days"}:
        p.append("policy must hold exactly gate_evidence_valid_days, language_approval_valid_days, layer_evidence_valid_days")
    else:
        for k, v in pol.items():
            if not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
                p.append(f"policy.{k} must be a positive integer")
    # pull requests
    prs = doc["pull_requests"]
    if not isinstance(prs, list):
        return p + ["pull_requests is not a list"]
    seen: set[Any] = set()
    for i, pr in enumerate(prs):
        w = f"pull_requests[{i}]"
        if not isinstance(pr, dict):
            p.append(f"{w}: not an object")
            continue
        need = {"number", "title", "branch", "head_sha", "merge_sha", "merged_at", "package", "ci", "recorded_by", "recorded_on"}
        for k in need - set(pr):
            p.append(f"{w}: missing {k!r}")
        for k in set(pr) - need:
            p.append(f"{w}: unknown field {k!r}")
        n = pr.get("number")
        if not (isinstance(n, int) and not isinstance(n, bool) and n > 0):
            p.append(f"{w}: number must be a positive integer")
        elif n in seen:
            p.append(f"{w}: duplicate PR number {n}")
        seen.add(n)
        for k in ("head_sha", "merge_sha"):
            if k in pr and not sha_ok(pr[k]):
                p.append(f"{w}: {k} malformed")
        if "merged_at" in pr and iso(pr["merged_at"]) is None:
            p.append(f"{w}: merged_at is not a valid date")
        if "recorded_on" in pr and iso(pr["recorded_on"]) is None:
            p.append(f"{w}: recorded_on is not a valid date")
        ci = pr.get("ci")
        if not isinstance(ci, dict) or set(ci) != {"result", "checks", "source", "url"}:
            p.append(f"{w}: ci must hold exactly result, checks, source, url")
        else:
            if ci["result"] not in CI_RESULTS:
                p.append(f"{w}: ci.result must be one of {list(CI_RESULTS)}")
            for k in ("checks", "source", "url"):
                if not isinstance(ci[k], str):
                    p.append(f"{w}: ci.{k} must be a string")
    # packages
    pk = doc["packages"]
    if not isinstance(pk, dict):
        return p + ["packages is not an object"]
    for pid, ent in pk.items():
        w = f"packages.{pid}"
        if not isinstance(ent, dict) or set(ent) != {"prs", "acceptance", "layers"}:
            p.append(f"{w}: must hold exactly prs, acceptance, layers")
            continue
        if not (isinstance(ent["prs"], list) and all(isinstance(x, int) and not isinstance(x, bool) for x in ent["prs"])):
            p.append(f"{w}: prs must be a list of integers")
        acc = ent["acceptance"]
        if not isinstance(acc, dict) or set(acc) != {"artefacts", "recorded_by", "recorded_on"}:
            p.append(f"{w}: acceptance must hold exactly artefacts, recorded_by, recorded_on")
        else:
            if not (isinstance(acc["artefacts"], list) and all(isinstance(x, str) for x in acc["artefacts"])):
                p.append(f"{w}: acceptance.artefacts must be a list of strings")
            if not _is_str(acc["recorded_by"]) or iso(acc["recorded_on"]) is None:
                p.append(f"{w}: acceptance.recorded_by/recorded_on invalid")
        lay = ent["layers"]
        if not isinstance(lay, dict) or set(lay) != set(LAYER_ORDER):
            p.append(f"{w}: layers must hold exactly {list(LAYER_ORDER)}")
            continue
        for ln in LAYER_ORDER:
            le = lay[ln]
            if not isinstance(le, dict) or not {"state", "evidence"} <= set(le) or set(le) - {"state", "evidence", "approver", "approved_on", "note"}:
                p.append(f"{w}.{ln}: must hold state and evidence (optional approver, approved_on, note)")
                continue
            if le["state"] not in LAYER_STATES[ln]:
                p.append(f"{w}.{ln}: state must be one of {list(LAYER_STATES[ln])}")
            if not isinstance(le["evidence"], list):
                p.append(f"{w}.{ln}: evidence must be a list")
            else:
                for j, ev in enumerate(le["evidence"]):
                    p += _evidence_entry_problems(f"{w}.{ln}.evidence[{j}]", ev)
    # gates
    g = doc["gates"]
    if not isinstance(g, dict):
        return p + ["gates is not an object"]
    for gid in PG_GATES:
        if gid not in g:
            p.append(f"gates.{gid}: missing")
    for gid, ent in g.items():
        w = f"gates.{gid}"
        if gid not in PG_GATES:
            p.append(f"{w}: unknown gate")
            continue
        if not isinstance(ent, dict) or set(ent) != {"state", "evidence", "recorded_by", "recorded_on"}:
            p.append(f"{w}: must hold exactly state, evidence, recorded_by, recorded_on")
            continue
        if ent["state"] not in GATE_STATES:
            p.append(f"{w}: state must be one of {list(GATE_STATES)}")
        if not isinstance(ent["evidence"], list):
            p.append(f"{w}: evidence must be a list")
        else:
            for j, ev in enumerate(ent["evidence"]):
                p += _evidence_entry_problems(f"{w}.evidence[{j}]", ev)
        if not _is_str(ent["recorded_by"]) or iso(ent["recorded_on"]) is None:
            p.append(f"{w}: recorded_by/recorded_on invalid")
    # language gates
    lg = doc["language_gates"]
    if not isinstance(lg, dict) or not lg:
        return p + ["language_gates must be a non-empty object"]
    for code, rec in lg.items():
        w = f"language_gates.{code}"
        if not isinstance(rec, dict) or not {"gates"} <= set(rec) or set(rec) - {"release_sha", "gates"}:
            p.append(f"{w}: must hold gates (optional release_sha)")
            continue
        if "release_sha" in rec and rec["release_sha"] is not None and not sha_ok(rec["release_sha"]):
            p.append(f"{w}: release_sha malformed")
        gates = rec["gates"]
        if not isinstance(gates, dict) or set(gates) != set(LG_GATES):
            p.append(f"{w}: gates must be exactly {LG_GATES[0]}..{LG_GATES[-1]}")
            continue
        for gid, ge in gates.items():
            if not isinstance(ge, dict) or "state" not in ge or set(ge) - {"state", "evidence", "approver", "approved_on", "release_sha", "approved_until", "note"}:
                p.append(f"{w}.{gid}: invalid entry")
            elif ge["state"] not in LA.STATES:
                p.append(f"{w}.{gid}: state must be one of {sorted(LA.STATES)}")
    return p


# ---------------------------------------------------------------------------------------------------------------- semantic checks
class Context:
    """What a check run is evaluated against: the date used for staleness, an optional release SHA and the repository root."""

    def __init__(self, today: date, release_sha: str | None = None, root: Path = ROOT):
        self.today, self.release_sha, self.root = today, release_sha, root


def _positive_evidence_problems(where: str, entries: list[dict], valid_days: int, ctx: Context) -> list[str]:
    """The rules for ANY positive state: an artefact link, SHA, date and a named-human or CI producer; fresh by date and (when bound) by release SHA."""
    p: list[str] = []
    if not entries:
        return [f"{where}: PASS without an artefact link (no evidence recorded)"]
    for j, e in enumerate(entries):
        w = f"{where} evidence[{j}]"
        if not link_ok(e.get("link"), ctx.root):
            p.append(f"{w}: PASS without a valid artefact link (an https URL or an existing repository file)")
        if e.get("produced_by_type") == "human" and not LA.named_human(e.get("produced_by")):
            p.append(f"{w}: human producer is not a named human")
        if e.get("produced_by_type") == "ci" and not _is_str(e.get("produced_by"), 3):
            p.append(f"{w}: CI producer (workflow or job) is not named")
        d = iso(e.get("date"))
        if d is None:
            p.append(f"{w}: no valid evidence date")
            continue
        if d > ctx.today:
            p.append(f"{w}: evidence date is in the future")
        vd = e.get("valid_days") if isinstance(e.get("valid_days"), int) else valid_days
        if is_stale(d, vd, ctx.today):
            p.append(f"{w}: stale (evidence dated {e['date']} is past its {vd}-day validity at {ctx.today.isoformat()})")
        if e.get("binding") == "release_sha" and ctx.release_sha and not same_sha(str(e.get("sha", "")), ctx.release_sha):
            p.append(f"{w}: stale (evidence is bound to release SHA {str(e.get('sha'))[:12]}, release is {ctx.release_sha[:12]})")
    return p


def language_problems(code: str, rec: dict, ctx: Context, valid_days: int) -> list[str]:
    """Language-gate PASS rules: ``language_activation.validate_locale_record`` is CALLED and every gate-level PASS problem it raises is a failure here (parity, never looser).
    Added on top (stricter only): the evidence must name a valid artefact link and the approval must be within the stated validity."""
    gates = {}
    for gid, ge in rec["gates"].items():
        g = {k: v for k, v in ge.items() if k != "note"}
        gates[gid] = g
    record = {"release_sha": rec.get("release_sha"), "gates": gates, "production_qualified": False, "offered_to_real_users": False}
    status = LA.validate_locale_record(code, record, today=ctx.today)
    out: list[str] = []
    for prob in status.problems:
        m = re.match(r"(LG-\d\d): (.*)", prob)
        if not m:
            continue   # locale-level findings (flag claims, release_sha of the locale) do not describe a PASS gate
        what = m.group(2)
        if what.startswith("state is ") or what == "invalid state":
            if what == "invalid state":
                out.append(f"language {code} {prob}")
            continue   # a non-PASS gate is not a violation: it is simply not passed
        out.append(f"language {code} {prob}")
    for gid, ge in rec["gates"].items():
        if ge["state"] != "PASS":
            continue
        if not links_in(ge.get("evidence"), ctx.root):
            out.append(f"language {code} {gid}: PASS without an artefact link in the evidence reference")
        d = LA._iso_date(ge.get("approved_on"))  # noqa: SLF001
        if d is not None and is_stale(d, valid_days, ctx.today):
            out.append(f"language {code} {gid}: stale (approval dated {ge['approved_on']} is past the {valid_days}-day validity)")
    return out


def _layer_problems(pid: str, ent: dict, ctx: Context, valid_days: int) -> list[str]:
    p: list[str] = []
    for ln in LAYER_ORDER:
        le = ent["layers"][ln]
        if le["state"] != POSITIVE[ln]:
            continue
        where = f"package {pid} layer {ln}"
        p += _positive_evidence_problems(where, le["evidence"], valid_days, ctx)
        if ln == "human_qualification":
            if not LA.named_human(le.get("approver")):
                p.append(f"{where}: COMPLETE without a named human approver")
            ad = iso(le.get("approved_on"))
            if ad is None:
                p.append(f"{where}: COMPLETE without a valid approval date")
            elif ad > ctx.today:
                p.append(f"{where}: approval date is in the future")
    return p


def check_ledger(doc: dict, ctx: Context, *, tracker_text: str | None = None, readiness: dict | None = None) -> tuple[list[str], list[str]]:
    """Return (failures, notes). Failures fail the check; notes are informational (never silent: they are printed)."""
    fails = schema_problems(doc)
    notes: list[str] = []
    if fails:
        return fails, notes            # semantic checks need a valid shape
    pol = doc["policy"]
    prs = {p["number"]: p for p in doc["pull_requests"]}
    for n, pr in prs.items():
        ci = pr["ci"]
        if ci["result"] == "success" and not (ci["source"].strip()):
            fails.append(f"PR #{n}: CI result 'success' recorded without a source")
        if pr["package"] is not None and pr["package"] not in E.BYID and pr["package"] != "PREP":
            fails.append(f"PR #{n}: unknown package {pr['package']!r}")
    # ---- packages: cross-check with PACKAGE_STATUS
    merged = merged_package_ids()
    for pid in merged:
        facts = package_pr_facts(pid)
        ent = doc["packages"].get(pid)
        if ent is None:
            fails.append(f"package {pid}: MERGED in PACKAGE_STATUS but has no ledger entry (run `release_evidence.py sync`)")
            continue
        if facts["pr"] not in ent["prs"]:
            fails.append(f"package {pid}: ledger PRs {ent['prs']} do not include PR #{facts['pr']} recorded in PACKAGE_STATUS")
        pr = prs.get(facts["pr"])
        if pr is None:
            fails.append(f"package {pid}: PR #{facts['pr']} is not in the ledger pull_requests")
            continue
        if facts["merge"] and not same_sha(pr["merge_sha"], facts["merge"]):
            fails.append(f"package {pid}: ledger merge SHA {pr['merge_sha'][:8]} contradicts PACKAGE_STATUS {facts['merge']}")
        if facts["head"] and not same_sha(pr["head_sha"], facts["head"]):
            fails.append(f"package {pid}: ledger head SHA {pr['head_sha'][:8]} contradicts PACKAGE_STATUS {facts['head']}")
    for pid, ent in doc["packages"].items():
        if pid not in E.PACKAGE_STATUS:
            fails.append(f"package {pid}: not in PACKAGE_STATUS")
        elif pid not in merged:
            fails.append(f"package {pid}: ledger has an entry but PACKAGE_STATUS does not record it as MERGED")
        for n in ent["prs"]:
            if n not in prs:
                fails.append(f"package {pid}: PR #{n} is not in the ledger pull_requests")
        for a in ent["acceptance"]["artefacts"]:
            if not link_ok(a, ctx.root):
                fails.append(f"package {pid}: acceptance artefact {a!r} is not an https URL or an existing repository file")
        fails += _layer_problems(pid, ent, ctx, pol["layer_evidence_valid_days"])
        # a positive layer must not contradict wave_matrix: LAYERS text still reading NOT RUN / OPEN is a contradiction
        live, human, _gate = W.LAYERS.get(pid, ("", "", ""))
        if ent["layers"]["live_staging"]["state"] == "PASS" and live.startswith(W.NS):
            fails.append(f"package {pid}: ledger live_staging PASS contradicts wave_matrix.LAYERS ({live[:40]}...)")
    # ---- production gates vs the tracker
    tr = tracker_gates(tracker_text)
    for gid in PG_GATES:
        ent = doc["gates"][gid]
        row = tr.get(gid)
        if row is None:
            fails.append(f"{gid}: not found in RELEASE_READINESS_TRACKER.md")
        elif row["state"] != ent["state"]:
            fails.append(f"{gid}: ledger state {ent['state']} contradicts tracker state {row['state']}")
        if ent["state"] == "PASS":
            fails += _positive_evidence_problems(gid, ent["evidence"], pol["gate_evidence_valid_days"], ctx)
            if row and row["packages"].strip().lower() != "all":
                for pid in [x.strip() for x in row["packages"].split(",")]:
                    if pid not in merged:
                        fails.append(f"{gid}: PASS contradicts package {pid}, which is not MERGED")
                    pe = doc["packages"].get(pid)
                    if pe is not None:
                        if pe["layers"]["live_staging"]["state"] == "NOT RUN":
                            fails.append(f"{gid}: PASS contradicts package {pid} live_staging NOT RUN")
                        if pe["layers"]["human_qualification"]["state"] == "OPEN":
                            fails.append(f"{gid}: PASS contradicts package {pid} human_qualification OPEN")
        elif ent["evidence"]:
            for j, ev in enumerate(ent["evidence"]):
                if not link_ok(ev.get("link"), ctx.root):
                    fails.append(f"{gid} evidence[{j}]: link is not an https URL or an existing repository file")
    for gid in tr:
        if gid not in doc["gates"]:
            fails.append(f"{gid}: in the tracker but not in the ledger")
    # ---- language gates
    if readiness is None:
        readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    rl = readiness.get("languages", {})
    counts = tracker_language_counts(tracker_text)
    eng_pass: dict[str, list[str]] = {}
    for code in rl:
        if code not in doc["language_gates"]:
            fails.append(f"language {code}: in language_readiness.json but not in the ledger")
    for code, rec in doc["language_gates"].items():
        if code not in rl:
            fails.append(f"language {code}: in the ledger but not in language_readiness.json")
            continue
        fails += language_problems(code, rec, ctx, pol["language_approval_valid_days"])
        led_pass = {g for g, ge in rec["gates"].items() if ge["state"] == "PASS"}
        jr = {g for g, ge in rl[code]["gates"].items() if ge.get("state") == "PASS"}
        for g in sorted(led_pass - jr):
            fails.append(f"language {code} {g}: ledger PASS contradicts language_readiness.json ({rl[code]['gates'][g].get('state')})")
        for g in sorted(jr - led_pass):
            eng_pass.setdefault(g, []).append(code)
        if code in counts and counts[code] != len(led_pass):
            fails.append(f"language {code}: tracker says {counts[code]} of 14 gates approved, ledger has {len(led_pass)}")
    for g in sorted(eng_pass):
        notes.append(f"{g}: language_readiness.json records PASS on engineering evidence for {', '.join(sorted(eng_pass[g]))}, but the ledger holds no human approval; not accepted as a passed gate")
    return fails, notes


def reconciliation_problems() -> list[str]:
    """The reconciliation check (PG-11): the committed reconciliation validates (read-only; offline)."""
    rec = _load(ROOT / "scripts/production/reconcile_issues.py", "reconcile_issues")
    doc = json.loads(rec.RECON.read_text(encoding="utf-8"))
    return [f"reconciliation: {e}" for e in rec.validate(doc)]


# ---------------------------------------------------------------------------------------------------------------- rendering (deterministic: no clock, sorted by register order)
def _ci_cell(pid: str, doc: dict) -> str:
    facts = package_pr_facts(pid)
    if not facts:
        return W.ci_layer(pid)
    pr = next((p for p in doc["pull_requests"] if p["number"] == facts["pr"]), None)
    if pr is None:
        return "NOT IN LEDGER"
    ci = pr["ci"]
    extra = f" ({ci['checks']})" if ci["checks"] else ""
    return f"PR #{pr['number']} CI {ci['result']}{extra}"


def package_layers(doc: dict) -> dict[str, dict]:
    """The five-layer inputs per package: engineering and CI derived (PACKAGE_STATUS + ledger), the other three from the ledger state with wave_matrix.LAYERS as the description."""
    out: dict[str, dict] = {}
    for p in E.PACKAGES:
        pid = p["id"]
        ent = doc["packages"].get(pid)
        live, human, gate = W.LAYERS[pid]
        row = {"engineering": W.eng_layer(pid), "ci": _ci_cell(pid, doc)}
        for ln, text in (("live_staging", live), ("human_qualification", human), ("gate_acceptance", gate)):
            if ent is None:
                row[ln] = {"state": "NOT IN LEDGER", "description": text, "evidence": []}
            else:
                le = ent["layers"][ln]
                row[ln] = {"state": le["state"], "description": text, "evidence": [e["link"] for e in le["evidence"]]}
        facts = package_pr_facts(pid)
        row["merge_sha"] = (next((x["merge_sha"] for x in doc["pull_requests"] if facts and x["number"] == facts["pr"]), "") or "")[:12] if facts else ""
        row["acceptance_artefacts"] = ent["acceptance"]["artefacts"] if ent else []
        out[pid] = row
    return out


def render_matrix_inputs(doc: dict) -> str:
    return json.dumps({"schema": "ask4mo.release_evidence_matrix_inputs.v1", "as_of": doc["as_of"], "packages": package_layers(doc)}, indent=1, ensure_ascii=False) + "\n"


def _evid_cell(ent: dict) -> str:
    return "; ".join(f"[{e['kind']}]({e['link']}) {e['date']} by {e['produced_by']}" for e in ent["evidence"]) or "none"


def render_view(doc: dict, tracker_text: str | None = None) -> str:
    tr = tracker_gates(tracker_text)
    merged = set(merged_package_ids())
    L = [
        "# Release Evidence View (generated)", "",
        f"Generated by `scripts/production/release_evidence.py generate` from `release_evidence_ledger.json` (as of {doc['as_of']}, main `{doc['main_sha'][:8]}`), `execution_packages.PACKAGE_STATUS`, `wave_matrix.LAYERS` and `RELEASE_READINESS_TRACKER.md`. **Do not edit by hand**; `check` fails when this file is stale.",
        "", "Nothing here is ever marked PASS automatically. A PASS needs a human-supplied or CI-produced artefact link in the ledger; engineering, CI, live staging, human qualification and gate acceptance are separate columns. Merged code is not a passed gate.", "",
        f"Evidence validity (stated policy): production gates {doc['policy']['gate_evidence_valid_days']} days, package layers {doc['policy']['layer_evidence_valid_days']} days, language approvals {doc['policy']['language_approval_valid_days']} days.", "",
        "## 1. Production gates PG-01 to PG-15", "",
        "| Gate | Name | Packages (merged: yes / no) | Ledger state | Tracker state | Evidence artefacts |", "|---|---|---|---|---|---|",
    ]
    for gid in PG_GATES:
        ent = doc["gates"][gid]
        row = tr.get(gid, {"name": "?", "packages": "?", "state": "?"})
        pk = row["packages"]
        if pk.strip().lower() == "all":
            pkcell = "all packages"
        else:
            pkcell = ", ".join(f"{x.strip()} ({'yes' if x.strip() in merged else 'no'})" for x in pk.split(","))
        L.append(f"| {gid} | {row['name']} | {pkcell} | {ent['state']} | {row['state']} | {_evid_cell(ent)} |")
    L += ["", "## 2. Pull requests (merged, with CI)", "", "| PR | Package | Branch | Head | Merge SHA | CI | Merged |", "|---|---|---|---|---|---|---|"]
    for pr in sorted(doc["pull_requests"], key=lambda x: x["number"]):
        ci = pr["ci"]
        L.append(f"| [#{pr['number']}]({pr_url(pr['number'])}) | {pr['package'] or 'docs/prep'} | {pr['branch']} | {pr['head_sha'][:8]} | {pr['merge_sha'][:8]} | {ci['result']}{' (' + ci['checks'] + ')' if ci['checks'] else ''} | {pr['merged_at']} |")
    L += ["", "## 3. Five-layer status per package", "", "| Package | 1 Engineering | 2 CI | 3 Live staging | 4 Human qualification | 5 Gate acceptance | Acceptance artefacts |", "|---|---|---|---|---|---|---|"]
    for pid, r in package_layers(doc).items():
        arts = ", ".join(f"[{Path(a).name}]({a})" if not a.startswith("http") else a for a in r["acceptance_artefacts"]) or "none"
        L.append(f"| {pid} | {r['engineering']} | {r['ci']} | {r['live_staging']['state']}: {r['live_staging']['description']} | {r['human_qualification']['state']}: {r['human_qualification']['description']} | {r['gate_acceptance']['state']}: {r['gate_acceptance']['description']} | {arts} |")
    L += ["", "## 4. Language gates LG-01 to LG-14 (per language)", "", "| Language | PASS | ENGINEERING DRAFT | NOT RUN | NOT STARTED | Gates with a human approval |", "|---|---|---|---|---|---|"]
    for code in sorted(doc["language_gates"]):
        gs = doc["language_gates"][code]["gates"]
        cnt = {s: sum(1 for g in gs.values() if g["state"] == s) for s in ("PASS", "ENGINEERING DRAFT", "NOT RUN", "NOT STARTED")}
        appr = sum(1 for g in gs.values() if g["state"] == "PASS" and LA.named_human(g.get("approver")))
        L.append(f"| {code} | {cnt['PASS']} | {cnt['ENGINEERING DRAFT']} | {cnt['NOT RUN']} | {cnt['NOT STARTED']} | {appr} of 14 |")
    L += ["", "No language is production-qualified: qualification needs all fourteen gates PASS with evidence, a named human approver, an approval date and the release SHA (`src/language_activation.py`).", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------------------------------------------- sync (never creates a positive state)
def blank_layers() -> dict:
    return {"live_staging": {"state": "NOT RUN", "evidence": []}, "human_qualification": {"state": "OPEN", "evidence": []}, "gate_acceptance": {"state": "NOT ACCEPTED", "evidence": []}}


def sync_ledger(doc: dict, *, git_facts: Callable[[int], dict] | None = None) -> list[str]:
    """Add, for every MERGED package in PACKAGE_STATUS without a ledger entry, a package entry and (when absent) a PR entry, from PACKAGE_STATUS only. Layers start NOT RUN / OPEN / NOT ACCEPTED
    and CI starts 'not recorded': a human or CI artefact must be added to the ledger to change that. Returns the added package ids."""
    added: list[str] = []
    for pid in merged_package_ids():
        if pid in doc["packages"]:
            continue
        facts = package_pr_facts(pid)
        if facts["pr"] not in {p["number"] for p in doc["pull_requests"]}:
            extra = git_facts(facts["pr"]) if git_facts else {}
            doc["pull_requests"].append({
                "number": facts["pr"], "title": extra.get("title", f"{pid} (from PACKAGE_STATUS)"), "branch": facts["branch"], "head_sha": facts["head"] or "0" * 7,
                "merge_sha": facts["merge"] or "0" * 7, "merged_at": extra.get("merged_at", doc["as_of"]), "package": pid,
                "ci": {"result": "not recorded", "checks": "", "source": "", "url": f"{pr_url(facts['pr'])}/checks"},
                "recorded_by": "release_evidence.py sync from PACKAGE_STATUS", "recorded_on": doc["as_of"]})
        ev = EXEC / "evidence" / f"{pid}_EVIDENCE.md"
        doc["packages"][pid] = {"prs": [facts["pr"]], "acceptance": {"artefacts": [ev.relative_to(ROOT).as_posix()] if ev.is_file() else [], "recorded_by": "release_evidence.py sync from PACKAGE_STATUS", "recorded_on": doc["as_of"]},
                                "layers": blank_layers()}
        added.append(pid)
    doc["pull_requests"].sort(key=lambda x: x["number"])
    return added


# ---------------------------------------------------------------------------------------------------------------- optional GitHub fetch (explicit opt-in; unauthenticated; never default; never in CI)
class RateLimited(Exception):
    def __init__(self, reset_epoch: int | None):
        super().__init__("GitHub API rate limit reached")
        self.reset_epoch = reset_epoch


def _get_json(url: str, opener: Callable, *, sleep: Callable[[float], None], now: Callable[[], float], max_wait: float) -> Any:
    """GET one public GitHub API URL. No credential is ever sent. A rate-limit response waits only if the reset is within ``max_wait`` seconds, else raises RateLimited."""
    import urllib.error  # lazy: the default path never imports a network client
    import urllib.request

    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ask4mo-release-evidence/1"})
    for attempt in range(2):
        try:
            resp = opener(req, timeout=20)
        except urllib.error.HTTPError as exc:
            hdr = exc.headers or {}
            limited = exc.code in (403, 429) and (hdr.get("X-RateLimit-Remaining") == "0" or hdr.get("Retry-After"))
            if not limited:
                raise
            reset = int(hdr["X-RateLimit-Reset"]) if hdr.get("X-RateLimit-Reset") else None
            wait = float(hdr["Retry-After"]) if hdr.get("Retry-After") else (reset - now() if reset else None)
            if attempt == 0 and wait is not None and 0 <= wait <= max_wait:
                sleep(wait + 1)
                continue
            raise RateLimited(reset) from exc
        with resp:
            remaining = resp.headers.get("X-RateLimit-Remaining")
            body = json.loads(resp.read().decode("utf-8"))
        if remaining == "0":
            body = {"_rate_limit_exhausted_after_this": True, **body} if isinstance(body, dict) else body
        return body
    raise RateLimited(None)


def fetch_pr_status(numbers: list[int], *, opener: Callable | None = None, sleep: Callable[[float], None] = time.sleep, now: Callable[[], float] = time.time, max_wait: float = 60.0) -> dict[int, dict]:
    """Read PR merge state and check-run conclusions from the public API. Returns {pr: {...}} and stops cleanly (partial result with 'rate_limited') when the limit is hit."""
    if opener is None:
        import urllib.request
        opener = urllib.request.urlopen
    out: dict[int, dict] = {}
    for n in numbers:
        try:
            pr = _get_json(f"https://api.github.com/repos/{REPO}/pulls/{n}", opener, sleep=sleep, now=now, max_wait=max_wait)
            head = pr["head"]["sha"]
            runs = _get_json(f"https://api.github.com/repos/{REPO}/commits/{head}/check-runs?per_page=100", opener, sleep=sleep, now=now, max_wait=max_wait)
        except RateLimited as rl:
            out[n] = {"rate_limited": True, "reset_epoch": rl.reset_epoch}
            break
        concl = [r.get("conclusion") for r in runs.get("check_runs", [])]
        out[n] = {"merged": bool(pr.get("merged")), "merge_sha": pr.get("merge_commit_sha") or "", "head_sha": head, "checks_total": len(concl),
                  "checks_success": sum(1 for c in concl if c == "success"), "all_success": bool(concl) and all(c == "success" for c in concl)}
    return out


def compare_fetched(doc: dict, fetched: dict[int, dict]) -> list[str]:
    """Differences between the ledger and GitHub. Reports only; never changes the ledger and never creates a PASS."""
    diffs: list[str] = []
    for pr in doc["pull_requests"]:
        f = fetched.get(pr["number"])
        if f is None:
            continue
        if f.get("rate_limited"):
            diffs.append(f"PR #{pr['number']}: not checked, GitHub rate limit reached (reset epoch {f.get('reset_epoch')}); re-run later")
            continue
        if not f["merged"]:
            diffs.append(f"PR #{pr['number']}: ledger says merged, GitHub says not merged")
        if f["merge_sha"] and not same_sha(f["merge_sha"], pr["merge_sha"]):
            diffs.append(f"PR #{pr['number']}: merge SHA differs (ledger {pr['merge_sha'][:8]}, GitHub {f['merge_sha'][:8]})")
        if f["head_sha"] and not same_sha(f["head_sha"], pr["head_sha"]):
            diffs.append(f"PR #{pr['number']}: head SHA differs (ledger {pr['head_sha'][:8]}, GitHub {f['head_sha'][:8]})")
        if pr["ci"]["result"] == "success" and not f["all_success"]:
            diffs.append(f"PR #{pr['number']}: ledger CI success but GitHub shows {f['checks_success']} of {f['checks_total']} successful check runs")
    return diffs


# ---------------------------------------------------------------------------------------------------------------- CLI
def view_problems(doc: dict) -> list[str]:
    out = []
    if not VIEW.is_file() or VIEW.read_text(encoding="utf-8") != render_view(doc):
        out.append(f"{VIEW.relative_to(ROOT)} is stale: run `python scripts/production/release_evidence.py generate`")
    if not MATRIX_INPUTS.is_file() or MATRIX_INPUTS.read_text(encoding="utf-8") != render_matrix_inputs(doc):
        out.append(f"{MATRIX_INPUTS.relative_to(ROOT)} is stale: run `python scripts/production/release_evidence.py generate`")
    return out


def run_check(*, today: date | None = None, release_sha: str | None = None, fetch: bool = False, out: Callable[[str], None] = print, fetcher: Callable[..., dict] | None = None) -> int:
    today = today or datetime.now(timezone.utc).date()
    doc = load_ledger()
    ctx = Context(today=today, release_sha=release_sha)
    fails, notes = check_ledger(doc, ctx)
    if not schema_problems(doc):
        fails += view_problems(doc)
    fails += reconciliation_problems()
    if fetch:
        nums = [p["number"] for p in doc["pull_requests"]]
        diffs = compare_fetched(doc, (fetcher or fetch_pr_status)(nums))
        fails += [f"fetch: {d}" for d in diffs]
    for n in notes:
        out(f"NOTE: {n}")
    if fails:
        out(f"FAIL: {len(fails)} problem(s)")
        for f in fails[:80]:
            out(f"  - {f}")
        return 1
    out(f"OK: release evidence ledger valid at {today.isoformat()} ({len(doc['pull_requests'])} PRs, {len(doc['packages'])} packages, 15 production gates, {len(doc['language_gates'])} languages x 14 gates); view fresh; reconciliation valid; nothing PASS without evidence")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["generate", "check", "sync"])
    ap.add_argument("--today", help="ISO date used for staleness (default: today UTC)")
    ap.add_argument("--release-sha", help="release SHA that release-bound evidence must match")
    ap.add_argument("--fetch", action="store_true", help="check only: compare with GitHub over the public unauthenticated API (opt-in; network)")
    a = ap.parse_args(argv)
    today = iso(a.today) if a.today else None
    if a.today and today is None:
        print("FAIL: --today is not a valid ISO date")
        return 2
    if a.fetch and a.command != "check":
        print("FAIL: --fetch applies to `check` only")
        return 2
    if a.command == "check":
        return run_check(today=today, release_sha=a.release_sha, fetch=a.fetch)
    doc = load_ledger()
    if a.command == "sync":
        added = sync_ledger(doc)
        LEDGER.write_text(dump_ledger(doc), encoding="utf-8")
        print(f"added {len(added)} package entr{'y' if len(added) == 1 else 'ies'}: {', '.join(added) or 'none'} (all NOT RUN / OPEN; no PASS is ever written)")
        return 0
    probs = schema_problems(doc)
    if probs:
        print("FAIL: ledger schema problems\n  - " + "\n  - ".join(probs[:30]))
        return 1
    VIEW.write_text(render_view(doc), encoding="utf-8")
    MATRIX_INPUTS.write_text(render_matrix_inputs(doc), encoding="utf-8")
    print(f"wrote {VIEW.relative_to(ROOT)} and {MATRIX_INPUTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
