#!/usr/bin/env python
"""01A (REVIEW-01 R1-R3, R6): offline prompt-injection corpus evaluator. REPORT ONLY unless ``--enforce`` is used.

Runs two existing, deterministic detectors over the labelled synthetic corpus in ``evaluations/injection/`` and reports the attack detection rate and the benign
false-positive rate overall, per category, per language, and for the frozen held-out split separately:

* ``input``  : ``src.security.detect_injection`` (the user-input guard).
* ``chunk``  : the retrieved-chunk screen (``src.copilot.security.rag_guard.screen_results``: risk score + quarantine).

No provider, network, model or paid call; no candidate data (the corpus is synthetic). It writes only to a temporary directory unless ``--write`` is passed.

Thresholds: owner-approved thresholds do NOT exist yet (OD-GATE-THRESHOLDS), so the default is report-only and exits 0 stating "thresholds not approved". ``--enforce``
reads ``evaluations/injection/thresholds.json`` (or ``--thresholds PATH``); that file is deliberately absent, and enforcing without it fails closed. This script never
invents a threshold. The held-out split must never be used to tune a detector.

    python scripts/eval_injection_corpus.py [--write] [--json PATH] [--enforce] [--thresholds PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (isolation: temporary DB, no .env, no developer store)

from src.copilot.models import DocumentChunk, RetrievalResult  # noqa: E402
from src.copilot.security.rag_guard import screen_results  # noqa: E402
from src.security import ALLOW, detect_injection  # noqa: E402

CORPUS_DIR = ROOT / "evaluations" / "injection"
CORPUS_PATH = CORPUS_DIR / "corpus.jsonl"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
THRESHOLDS_PATH = CORPUS_DIR / "thresholds.json"
REPORT_PATH = CORPUS_DIR / "last_report.json"
SCHEMA_VERSION = 1
HELDOUT_PERCENT = 30  # ids whose sha256 mod 100 is below this are held out
ATTACK, BENIGN = "attack", "benign"
THRESHOLDS_NOT_APPROVED = "thresholds not approved"


# ---------------------------------------------------------------- corpus + split ---------------------------------------------------------------------------------
def split_of(case_id: str) -> str:
    """Deterministic split: a hash of the id alone (never of the text or of any detector result)."""
    return "heldout" if int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16) % 100 < HELDOUT_PERCENT else "dev"


def load_corpus(path: Path = CORPUS_PATH) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for case in cases:
        case["split"] = split_of(case["id"])
    return cases


def corpus_sha256(path: Path = CORPUS_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def heldout_hash(cases: list[dict]) -> str:
    """Hash of the held-out membership: sorted (id, text-hash) pairs, so neither the membership nor any held-out text can change unnoticed."""
    rows = sorted((c["id"], hashlib.sha256(c["text"].encode("utf-8")).hexdigest()) for c in cases if c["split"] == "heldout")
    return hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()


def manifest_for(cases: list[dict]) -> dict:
    by_split = defaultdict(lambda: {ATTACK: 0, BENIGN: 0})
    for c in cases:
        by_split[c["split"]][c["label"]] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_file": "corpus.jsonl",
        "corpus_sha256": corpus_sha256(),
        "case_count": len(cases),
        "split_rule": f"sha256(case id) mod 100 < {HELDOUT_PERCENT} -> heldout, else dev",
        "heldout_percent": HELDOUT_PERCENT,
        "heldout_sha256": heldout_hash(cases),
        "counts": {k: dict(v) for k, v in sorted(by_split.items())},
        "synthetic_only": True,
        "tuning_rule": "Detectors may be tuned on the dev split only. The held-out split is measured, never tuned against.",
    }


# ---------------------------------------------------------------- detectors --------------------------------------------------------------------------------------
def run_detectors(text: str) -> dict:
    """Return per-detector verdicts. No raw text is returned."""
    assessment = detect_injection(text)
    chunk = RetrievalResult(chunk=DocumentChunk(chunk_id="c", doc_id="d", text=text if text.strip() else "-"), score=1.0)
    screen = screen_results([chunk])
    chunk_blocked = screen.quarantined_count == 1
    chunk_flagged = chunk_blocked or bool(screen.warned)
    return {
        "input_flagged": assessment.decision != ALLOW,
        "input_blocked": assessment.is_blocked,
        "chunk_flagged": chunk_flagged,
        "chunk_blocked": chunk_blocked,
        "chunk_risk": screen.max_risk,
    }


def evaluate(cases: list[dict]) -> list[dict]:
    rows = []
    for case in cases:
        verdict = run_detectors(case["text"])
        verdict["any_flagged"] = verdict["input_flagged"] or verdict["chunk_flagged"]
        verdict["any_blocked"] = verdict["input_blocked"] or verdict["chunk_blocked"]
        rows.append({"id": case["id"], "label": case["label"], "category": case["category"], "language": case["language"], "surface": case["surface"], "split": case["split"], **verdict})
    return rows


# ---------------------------------------------------------------- metrics ----------------------------------------------------------------------------------------
_DETECTORS = ("input_flagged", "input_blocked", "chunk_flagged", "chunk_blocked", "any_flagged", "any_blocked")


def _rate(hit: int, total: int) -> float | None:
    return round(hit / total, 4) if total else None


def summarize(rows: list[dict]) -> dict:
    attacks = [r for r in rows if r["label"] == ATTACK]
    benign = [r for r in rows if r["label"] == BENIGN]
    out = {"attacks": len(attacks), "benign": len(benign)}
    for det in _DETECTORS:
        out[f"detection_rate_{det}"] = _rate(sum(r[det] for r in attacks), len(attacks))
        out[f"false_positive_rate_{det}"] = _rate(sum(r[det] for r in benign), len(benign))
    return out


def build_report(cases: list[dict], *, dev_only: bool = False) -> dict:
    """``dev_only`` evaluates the development split alone: the held-out cases are never run through a detector (used while designing detector changes)."""
    rows = evaluate([c for c in cases if c["split"] == "dev"] if dev_only else cases)
    groups: dict[str, dict] = {}
    for key in ("category", "language", "surface", "split"):
        buckets: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            buckets[r[key]].append(r)
        groups[f"by_{key}"] = {name: summarize(items) for name, items in sorted(buckets.items())}
    heldout = [r for r in rows if r["split"] == "heldout"]
    dev = [r for r in rows if r["split"] == "dev"]
    manifest = manifest_for(cases)
    # Per-case ids are emitted for the DEVELOPMENT split only: held-out misses and false positives are never listed (strict held-out discipline).
    misses = sorted(r["id"] for r in dev if r["label"] == ATTACK and not r["any_flagged"])
    false_positives = sorted(r["id"] for r in dev if r["label"] == BENIGN and r["any_flagged"])
    return {
        "schema_version": SCHEMA_VERSION,
        "thresholds_status": THRESHOLDS_NOT_APPROVED,
        "mode": "report-only",
        "corpus_sha256": manifest["corpus_sha256"],
        "heldout_sha256": manifest["heldout_sha256"],
        "case_count": len(rows),
        "dev_only_run": dev_only,
        "error_analysis_scope": "dev split only (held-out per-case results are never emitted)",
        "detectors": {"input": "src.security.detect_injection", "chunk": "src.copilot.security.rag_guard.screen_results"},
        "definitions": {
            "flagged": "warn or block (input) / warned or quarantined (chunk)",
            "blocked": "block (input) / quarantined (chunk)",
            "detection_rate": "share of attack cases flagged/blocked",
            "false_positive_rate": "share of benign cases flagged/blocked",
        },
        "overall": summarize(rows),
        "dev": summarize(dev),
        "heldout": summarize(heldout),
        **groups,
        "missed_attack_ids": misses,
        "benign_false_positive_ids": false_positives,
        "limitations": [
            "Small synthetic corpus: rates have wide uncertainty and per-language cells are tiny.",
            "Both detectors are heuristic; a high rate here is not evidence of safety against unseen attacks.",
            "Structural controls (labelled data blocks, tool authorization in 01D, output guard) remain the primary defence.",
        ],
    }


# ---------------------------------------------------------------- enforcement ------------------------------------------------------------------------------------
def load_thresholds(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def check_thresholds(report: dict, thresholds: dict) -> list[str]:
    """Return the failures against owner-approved thresholds (held-out split). Expected keys (all optional, none has a default):
    approved_by, approved_on, heldout.min_detection_rate_{any_flagged,any_blocked}, heldout.max_false_positive_rate_{any_flagged,any_blocked}."""
    failures: list[str] = []
    if not thresholds.get("approved_by") or not thresholds.get("approved_on"):
        return ["thresholds file lacks approved_by/approved_on: not an owner-approved file"]
    limits = thresholds.get("heldout") or {}
    if not limits:
        return ["thresholds file defines no heldout limits"]
    held = report["heldout"]
    for key, limit in limits.items():
        if key.startswith("min_"):
            metric = key[len("min_"):]
            value = held.get(metric)
            if value is None or value < limit:
                failures.append(f"heldout {metric}={value} below approved minimum {limit}")
        elif key.startswith("max_"):
            metric = key[len("max_"):]
            value = held.get(metric)
            if value is None or value > limit:
                failures.append(f"heldout {metric}={value} above approved maximum {limit}")
        else:
            failures.append(f"unknown threshold key {key!r}")
    return failures


# ---------------------------------------------------------------- output -----------------------------------------------------------------------------------------
def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:5.1f}%"


def render(report: dict) -> str:
    lines = [f"Injection corpus evaluation: {report['case_count']} cases, {report['thresholds_status'].upper()} ({report['mode']})",
             f"corpus sha256 {report['corpus_sha256'][:16]}  heldout sha256 {report['heldout_sha256'][:16]}", ""]
    header = f"{'group':<22}{'atk':>5}{'ben':>5}  {'det(flag)':>10}{'det(block)':>11}{'FP(flag)':>10}{'FP(block)':>11}"
    lines.append(header)

    def line(name: str, s: dict) -> str:
        return (f"{name:<22}{s['attacks']:>5}{s['benign']:>5}  {_fmt(s['detection_rate_any_flagged']):>10}{_fmt(s['detection_rate_any_blocked']):>11}"
                f"{_fmt(s['false_positive_rate_any_flagged']):>10}{_fmt(s['false_positive_rate_any_blocked']):>11}")

    lines.append(line("OVERALL", report["overall"]))
    lines.append(line("dev split", report["dev"]))
    lines.append(line("HELD-OUT split", report["heldout"]))
    for key in ("by_category", "by_language", "by_surface"):
        lines.append(f"-- {key[3:]}")
        for name, s in report[key].items():
            lines.append(line("  " + name, s))
    lines.append(f"missed attacks: {len(report['missed_attack_ids'])}; benign false positives: {len(report['benign_false_positive_ids'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write evaluations/injection/last_report.json (default: temp dir only)")
    parser.add_argument("--json", metavar="PATH", help="also write the JSON report here")
    parser.add_argument("--enforce", action="store_true", help="fail on owner-approved thresholds; fails closed when none exist")
    parser.add_argument("--dev-only", action="store_true", help="run the development split only; the held-out split is not evaluated at all")
    parser.add_argument("--thresholds", metavar="PATH", default=str(THRESHOLDS_PATH))
    args = parser.parse_args(argv)

    cases = load_corpus()
    report = build_report(cases, dev_only=args.dev_only)
    print(render(report))

    if args.write:
        dest = REPORT_PATH
    else:
        dest = Path(tempfile.mkdtemp(prefix="inj_corpus_")) / "report.json"
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"report: {dest}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.enforce and args.dev_only:
        print("ENFORCE FAILED CLOSED: --enforce needs the held-out split; do not combine it with --dev-only.")
        return 3
    if not args.enforce:
        print(f"{THRESHOLDS_NOT_APPROVED}: REPORT ONLY (exit 0). Owner-approved thresholds are pending (OD-GATE-THRESHOLDS).")
        return 0
    thresholds = load_thresholds(Path(args.thresholds))
    if thresholds is None:
        print(f"ENFORCE FAILED CLOSED: {THRESHOLDS_NOT_APPROVED}; no thresholds file at {args.thresholds}. Nothing is invented.")
        return 3
    failures = check_thresholds(report, thresholds)
    for failure in failures:
        print("FAIL:", failure)
    print("ENFORCE:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
