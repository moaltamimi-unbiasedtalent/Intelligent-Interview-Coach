"""Independent human AI evaluation PROTOCOL and HARNESS (06G; PG-07; OD-BUDGET, OD-GATE-THRESHOLDS). Extends the 06C blinded rating harness (``rating.py``).

What 06G adds to 06C
* a larger, stratified review sample (``extended`` roles) and at least three independent raters per language;
* reviewer independence rules and a conflict-of-interest declaration that is validated, never assumed;
* sample-size and power guidance per language with HONEST intervals (item-level t interval, Wilson interval, rule-of-three upper bound);
* inter-rater agreement computed offline: Cohen's kappa (unweighted and weighted) and Krippendorff's alpha (nominal, ordinal, interval) with a seeded bootstrap interval;
* a results schema with a validator and a report generator.

Boundaries (never blur)
* There is NO PASS anywhere. ``approved`` is always false; thresholds are the owner's (OD-GATE-THRESHOLDS): the proposals below are labelled PROPOSAL and are compared only
  informationally. ``render_report_md`` raises if its own output contains the word PASS in capitals.
* No model call, no network, no credential in this module. The generation step that could spend money is ``human_eval_generate.py`` and it refuses without an approved budget marker,
  a ceiling and the 05C governor.
* No real reviewer data and no invented names: declarations are completed by the people the owner appoints (OD-LANG-03); the self-test uses obviously synthetic labels in a temp directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import statistics
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.language_activation import named_human
from src.language_quality import rating as R

ROOT = Path(__file__).resolve().parents[2]
EXTENSION_FILE = ROOT / "evaluations" / "language_ai" / "human_eval_bank_extension.json"
SCHEMA_FILE = ROOT / "evaluations" / "language_ai" / "human_eval_results.schema.json"
DECLARATION_TEMPLATE_FILE = ROOT / "evaluations" / "language_ai" / "reviewer_declaration.template.json"
PROTOCOL_VERSION = "06G/1"
RESULT_SCHEMA_ID = "ask4mo.language_ai.human_eval_result/1"
REPORT_SCHEMA_ID = "ask4mo.language_ai.human_eval_report/1"
DECLARATION_SCHEMA_ID = "ask4mo.language_ai.reviewer_declaration/1"
LANGUAGES = R.LANGUAGES
DIMENSIONS = R.DIMENSIONS
FLAGS = R.FLAGS
MIN_RATERS = 3                      # protocol minimum per language (06C allowed 2; 3 makes Krippendorff's alpha and a majority meaningful)
NOT_NAMED = "NOT NAMED (OD-LANG-03)"
THRESHOLDS_NOT_SET = "NOT SET: owner-approved thresholds are required (OD-GATE-THRESHOLDS). Proposals below are PROPOSALS, not adopted."

STATUSES: tuple[str, ...] = ("INCOMPLETE", "RATERS_INSUFFICIENT", "REVIEWERS_UNVERIFIED", "REVIEWERS_NOT_INDEPENDENT", "CONTROLS_FAILED", "READY_FOR_OWNER_REVIEW", "SELFTEST_ONLY")

# Labelled PROPOSALS for the owner to approve, change or reject (OD-GATE-THRESHOLDS). Nothing here is adopted and nothing in the code turns a comparison into an approval.
PROPOSED_LEVELS: dict[str, Any] = {
    "label": "PROPOSAL, NOT ADOPTED (OD-GATE-THRESHOLDS)",
    "mean_rating_min": 4.0, "lower_95_bound_min": 3.5, "share_4_or_5_min": 0.80, "unsafe_content_upper95_max": 0.10, "wrong_language_upper95_max": 0.10,
    "krippendorff_alpha_ordinal_min": 0.667, "min_raters": MIN_RATERS, "min_items_per_language": 60,
    "basis": "Mean of 4 of 5 on every dimension; Krippendorff's commonly cited tentative 0.667 for alpha; upper bounds that a modest sample can actually demonstrate. The owner decides.",
}


# ------------------------------------------------------------------------------------------------------------------------------------------------ sample
def load_extension(path: Path | None = None) -> dict:
    return json.loads((path or EXTENSION_FILE).read_text(encoding="utf-8"))


def merged_bank(extended: bool = True) -> dict:
    """The 06C synthetic bank, plus (when ``extended``) the 06G extra profession-neutral roles, so each language has 12 roles x 5 task kinds = 60 model outputs."""
    bank = R.load_bank()
    if not extended:
        return bank
    ext = load_extension()
    roles = dict(bank["roles"])
    for key, role in ext["roles"].items():
        if key in roles:
            raise ValueError(f"extension role {key!r} duplicates a base role")
        for lang in LANGUAGES:
            if not str(role.get(lang, "")).strip():
                raise ValueError(f"extension role {key!r} missing {lang}")
        roles[key] = role
    return {**bank, "roles": roles}


def prompt_items(extended: bool = True) -> list[dict[str, str]]:
    return R.prompt_items(merged_bank(extended))


def build_evaluation_packet(outputs: Iterable[Mapping[str, str]], out_dir: Path, *, seed: str | None = None, raters: int = MIN_RATERS, fake: bool = False, extended: bool = True) -> dict:
    """The 06C packet over the 06G sample. Reviewers receive the same files as in 06C (a test pins the list); the private manifest is relabelled 06G."""
    if raters < MIN_RATERS:
        raise ValueError(f"06G requires at least {MIN_RATERS} independent raters per language")
    manifest = R.build_packet(outputs, out_dir, seed=seed, raters=raters, fake=fake, bank=merged_bank(extended))
    manifest.update({"package": "06G", "protocol": PROTOCOL_VERSION, "extended_roles": extended, "gate_ids": ["PG-07", "LG-04", "LG-05"]})
    (Path(out_dir) / "private" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return manifest


# ------------------------------------------------------------------------------------------------------------------------------------------------ statistics (honest intervals)
_T95: dict[int, float] = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
                          16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
                          30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}
Z95, Z80_POWER = 1.959964, 0.841621


def t_critical_95(df: int) -> float:
    """Two-sided 95 percent t value; between table rows the LARGER (lower df) value is used, so intervals are never too narrow."""
    if df < 1:
        raise ValueError("degrees of freedom must be at least 1")
    if df > 120:
        return Z95
    return _T95[max(k for k in _T95 if k <= df)]


def mean_ci95(values: Sequence[float]) -> dict[str, float | int | None]:
    """Mean with a 95 percent t interval over INDEPENDENT units (here: items, each the mean of its raters). Rater effects are not modelled, so the interval understates uncertainty a little."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "low": None, "high": None}
    mean = statistics.fmean(values)
    if n < 2:
        return {"n": n, "mean": round(mean, 3), "sd": None, "low": None, "high": None}
    sd = statistics.stdev(values)
    half = t_critical_95(n - 1) * sd / math.sqrt(n)
    return {"n": n, "mean": round(mean, 3), "sd": round(sd, 3), "low": round(mean - half, 3), "high": round(mean + half, 3)}


def wilson_interval95(k: int, n: int) -> tuple[float, float]:
    """Wilson score interval for a proportion (valid at 0 and n, unlike the normal approximation)."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError("need 0 <= k <= n and n > 0")
    p = k / n
    z2 = Z95 ** 2
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def upper95_if_zero(n: int) -> float:
    """Rule of three: with 0 events in n independent items the 95 percent upper bound on the rate is about 3/n."""
    if n <= 0:
        raise ValueError("n must be positive")
    return round(min(1.0, 3.0 / n), 4)


def n_for_mean_halfwidth(sd: float, half_width: float) -> int:
    """Items needed so a 95 percent interval for a mean is at most +-half_width (normal approximation, plus 2 for the t correction)."""
    if sd <= 0 or half_width <= 0:
        raise ValueError("sd and half_width must be positive")
    return math.ceil((Z95 * sd / half_width) ** 2) + 2


def n_per_group_for_difference(sd: float, diff: float) -> int:
    """Items per language needed to detect a true mean difference of ``diff`` between two languages with 80 percent power at a two-sided 5 percent level."""
    if sd <= 0 or diff <= 0:
        raise ValueError("sd and diff must be positive")
    return math.ceil(2 * ((Z95 + Z80_POWER) * sd / diff) ** 2) + 2


def n_for_zero_event_bound(max_rate: float) -> int:
    """Items with ZERO events needed to show (95 percent) that a rate is below ``max_rate``."""
    if not 0 < max_rate < 1:
        raise ValueError("max_rate must be between 0 and 1")
    return math.ceil(3.0 / max_rate)


def guidance() -> dict[str, Any]:
    sds, halves = (0.8, 1.0, 1.2), (0.5, 0.4, 0.3, 0.25, 0.2)
    return {"sd": sds, "half_widths": halves,
            "mean_n": {str(sd): {str(h): n_for_mean_halfwidth(sd, h) for h in halves} for sd in sds},
            "diff_n": {str(sd): {str(d): n_per_group_for_difference(sd, d) for d in (0.8, 0.6, 0.5, 0.4, 0.3)} for sd in sds},
            "zero_event_n": {str(r): n_for_zero_event_bound(r) for r in (0.10, 0.05, 0.02, 0.01)},
            "achievable": {str(n): {str(sd): round(t_critical_95(n - 1) * sd / math.sqrt(n), 2) for sd in sds} for n in (30, 60, 90, 120)}}


def render_guidance_md() -> str:
    g = guidance()
    out = ["# 06G sample-size and power guidance (generated)", "",
           "Generated by `python scripts/language_human_eval.py guidance --write`; do not edit by hand (a test fails if it drifts). Offline, deterministic, no model call.", "",
           "This guidance is PER LANGUAGE: each language is analysed on its own and no pooled claim across languages is made (LG-13). The numbers are engineering guidance for the owner, "
           "not thresholds (OD-GATE-THRESHOLDS) and not a qualification.", "",
           "Unit of analysis. The unit is the ITEM (a model output), rated by several raters; an item's rating is the mean of its raters. Ratings of the same item by different raters are not "
           "independent, so only the number of ITEMS counts for the intervals below. Rater effects (one rater harsher than another) are not modelled; with three raters the interval is "
           "somewhat too narrow, which is why agreement is reported next to it. The spread `sd` of an item's rating across items is unknown until a pilot; 1.0 on the 1 to 5 scale is a "
           "typical assumption, 0.8 and 1.2 bracket it. Re-estimate it from the first language rated before sizing the rest.", "",
           "## Items needed so the 95 percent interval for a mean rating is +-h", "", "| sd | " + " | ".join(f"h = {h}" for h in g["half_widths"]) + " |", "|---|" + "---|" * len(g["half_widths"])]
    for sd in g["sd"]:
        out.append(f"| {sd} | " + " | ".join(str(g["mean_n"][str(sd)][str(h)]) for h in g["half_widths"]) + " |")
    out += ["", "## What a given number of items achieves (half-width of the 95 percent interval, scale points)", "", "| items | " + " | ".join(f"sd {sd}" for sd in g["sd"]) + " |", "|---|" + "---|" * len(g["sd"])]
    for n, row in g["achievable"].items():
        out.append(f"| {n} | " + " | ".join(str(row[str(sd)]) for sd in g["sd"]) + " |")
    out += ["", "The 06C sample (30 outputs per language) therefore pins a mean only to about +-0.4 at sd 1.0; the 06G extended sample (60 outputs per language) to about +-0.3. "
            "Neither can support a precise per-language claim.", "",
            "## Items per language needed to detect a true difference between two languages (80 percent power, two-sided 5 percent)", "",
            "| sd | " + " | ".join(f"diff {d}" for d in (0.8, 0.6, 0.5, 0.4, 0.3)) + " |", "|---|---|---|---|---|---|"]
    for sd in g["sd"]:
        out.append(f"| {sd} | " + " | ".join(str(g["diff_n"][str(sd)][str(d)]) for d in (0.8, 0.6, 0.5, 0.4, 0.3)) + " |")
    out += ["", "## Items with ZERO events needed to show a rate is below a bound (95 percent, rule of three)", "", "| bound on the rate | items |", "|---|---|"]
    for r, n in g["zero_event_n"].items():
        out.append(f"| {float(r):.0%} | {n} |")
    out += ["", "So 60 clean items show only that an unsafe or wrong-language rate is probably below 5 percent; they cannot show it is below 1 percent. One observed event in 60 items already "
            "gives a 95 percent Wilson upper bound of roughly 9 percent.", "",
            "## Agreement sample", "",
            "Krippendorff's alpha and kappa need variation in the ratings and at least two raters on the same items; at least three raters (the 06G minimum) keep alpha defined when a rater "
            "is excluded. The bootstrap interval for alpha resamples items and is wide at 60 items; report it, do not hide it.", "",
            "## Decision for the owner (OD-BUDGET, OD-GATE-THRESHOLDS)", "",
            "1. Choose the interval width you need per language (column h) and the spread you assume (row sd); read the items needed. 2. Price that many generated outputs with the 05C governor "
            "before approving the budget. 3. Decide the thresholds; the report compares to PROPOSALS only until you do.", ""]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------------------------------------------------------ agreement
def cohen_kappa(a: Sequence[Any], b: Sequence[Any], *, weights: str = "none", categories: Sequence[Any] | None = None) -> float | None:
    """Cohen's kappa for two raters. ``weights`` is ``none``, ``linear`` or ``quadratic`` (the weighted forms need ordered numeric categories). ``None`` when undefined."""
    if len(a) != len(b) or not a:
        return None
    cats = sorted(categories if categories is not None else set(a) | set(b))
    if len(cats) < 2:
        return None
    k = len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    n = float(len(a))
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:
        d = abs(i - j) / (k - 1)
        return 0.0 if i == j and weights == "none" else (1.0 if weights == "none" else (d if weights == "linear" else d * d))

    if weights not in ("none", "linear", "quadratic"):
        raise ValueError("weights must be none, linear or quadratic")
    num = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w(i, j) * row[i] * col[j] / n for i in range(k) for j in range(k))
    return None if den == 0 else round(1 - num / den, 4)


def krippendorff_alpha(units: Sequence[Sequence[Any]], level: str = "ordinal") -> float | None:
    """Krippendorff's alpha. ``units`` holds, per unit (item), the values given by the raters; ``None`` marks a missing rating. ``level`` is nominal, ordinal or interval.
    ``None`` is returned when alpha is undefined (fewer than two pairable values, or no variation expected)."""
    if level not in ("nominal", "ordinal", "interval"):
        raise ValueError("level must be nominal, ordinal or interval")
    coincide: dict[tuple[Any, Any], float] = {}
    for unit in units:
        vals = [v for v in unit if v is not None]
        m = len(vals)
        if m < 2:
            continue
        for i, x in enumerate(vals):
            for j, y in enumerate(vals):
                if i != j:
                    coincide[(x, y)] = coincide.get((x, y), 0.0) + 1.0 / (m - 1)
    cats = sorted({c for pair in coincide for c in pair})
    n_c = {c: sum(coincide.get((c, k), 0.0) for k in cats) for c in cats}
    n = sum(n_c.values())
    if n <= 1 or len(cats) < 2:
        return None

    def delta2(c: Any, k: Any) -> float:
        if c == k:
            return 0.0
        if level == "nominal":
            return 1.0
        if level == "interval":
            return float(c - k) ** 2
        lo, hi = (c, k) if c < k else (k, c)
        between = sum(n_c[g] for g in cats if lo <= g <= hi)
        return (between - (n_c[lo] + n_c[hi]) / 2.0) ** 2

    d_o = sum(coincide.get((c, k), 0.0) * delta2(c, k) for c in cats for k in cats) / n
    d_e = sum(n_c[c] * n_c[k] * delta2(c, k) for c in cats for k in cats) / (n * (n - 1))
    return None if d_e == 0 else round(1 - d_o / d_e, 4)


def krippendorff_ci95(units: Sequence[Sequence[Any]], level: str = "ordinal", *, seed: str = "06G", resamples: int = 1000) -> tuple[float | None, float | None]:
    """Seeded percentile bootstrap over units (items). ``(None, None)`` when too few resamples have a defined alpha."""
    rng = random.Random(seed)
    n = len(units)
    vals: list[float] = []
    for _ in range(resamples):
        a = krippendorff_alpha([units[rng.randrange(n)] for _ in range(n)], level)
        if a is not None:
            vals.append(a)
    if len(vals) < resamples // 2:
        return (None, None)
    vals.sort()
    return (vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))])


def alpha_band(alpha: float | None) -> str:
    """Descriptive band only (Krippendorff's tentative guidance 0.667 and 0.800). Not a gate; the owner sets thresholds."""
    if alpha is None:
        return "undefined"
    return "below 0.667 (low)" if alpha < 0.667 else ("0.667 to 0.800 (tentative)" if alpha < 0.8 else "0.800 or above (good)")


# ------------------------------------------------------------------------------------------------------------------------------------------------ independence
DECLARATION_BOOLEANS: dict[str, bool] = {   # field -> the value that is compatible with independence
    "is_author_of_reviewed_text": False, "contributed_to_prompts_or_translations": False, "compensation_depends_on_outcome": False, "paid_by_author_or_author_affiliate": False,
    "has_financial_interest_in_outcome": False, "confirms_no_translation_or_ai_tools": True, "confirms_rates_separately_from_other_raters": True,
}


def declaration_template(language: str = "", slot: str = "") -> dict[str, Any]:
    """The BLANK conflict-of-interest declaration. Booleans are null until the reviewer answers; nothing is pre-filled."""
    return {"schema": DECLARATION_SCHEMA_ID, "language": language, "rater_slot": slot, "reviewer_name": "", "native_or_fluent_statement": "",
            **{k: None for k in DECLARATION_BOOLEANS}, "relationships_to_owner_or_product": "", "other_conflicts": "", "explanation_if_any_flag_differs": "",
            "declaration_date": "", "typed_signature": "",
            "note": "BLANK TEMPLATE. The author of the text under review is the engineering side (text written and machine-translated with AI assistance). Answer every field truthfully; write NONE where there is nothing to declare."}


def validate_declaration(decl: Mapping[str, Any], *, today: date | None = None) -> tuple[str, list[str]]:
    """(status, problems). Status is ``INCOMPLETE``, ``OWNER_DECISION_REQUIRED`` (a conflict flag is raised) or ``ELIGIBLE_FOR_OWNER_APPOINTMENT``.
    It is never an appointment: only the owner appoints (OD-LANG-03)."""
    now = today or datetime.now(timezone.utc).date()
    problems: list[str] = []
    if decl.get("schema") != DECLARATION_SCHEMA_ID:
        problems.append("schema is not the declaration schema")
    if decl.get("language") not in LANGUAGES:
        problems.append("language is not an active candidate language")
    if not re.fullmatch(r"rater_R\d+", str(decl.get("rater_slot", ""))):
        problems.append("rater_slot must look like rater_R1")
    if not named_human(decl.get("reviewer_name")):
        problems.append("reviewer_name is not a named human")
    if not (isinstance(decl.get("native_or_fluent_statement"), str) and len(decl["native_or_fluent_statement"].strip()) >= 15):
        problems.append("native_or_fluent_statement is missing")
    conflict = False
    for field, ok_value in DECLARATION_BOOLEANS.items():
        v = decl.get(field)
        if not isinstance(v, bool):
            problems.append(f"{field} must be answered true or false")
        elif v is not ok_value:
            conflict = True
    for field in ("relationships_to_owner_or_product", "other_conflicts"):
        v = decl.get(field)
        if not (isinstance(v, str) and v.strip()):
            problems.append(f"{field} is empty (write NONE explicitly)")
        elif v.strip().upper() != "NONE":
            conflict = True
    try:
        d = date.fromisoformat(str(decl.get("declaration_date")))
        if d > now:
            problems.append("declaration_date is in the future")
    except ValueError:
        problems.append("declaration_date is not a valid ISO date")
    if str(decl.get("typed_signature", "")).strip().casefold() != str(decl.get("reviewer_name", "")).strip().casefold() or not str(decl.get("typed_signature", "")).strip():
        problems.append("typed_signature must equal reviewer_name")
    if problems:
        return "INCOMPLETE", problems
    if conflict:
        if not (isinstance(decl.get("explanation_if_any_flag_differs"), str) and len(decl["explanation_if_any_flag_differs"].strip()) >= 20):
            return "INCOMPLETE", ["a conflict is declared but explanation_if_any_flag_differs is missing"]
        return "OWNER_DECISION_REQUIRED", []
    return "ELIGIBLE_FOR_OWNER_APPOINTMENT", []


def check_independence(declarations: Mapping[str, Mapping[str, Any]], language: str, expected_raters: int, *, today: date | None = None) -> dict[str, Any]:
    """Across the rater slots of one language. ``declarations`` is ``{rater_slot: declaration}``."""
    per: dict[str, dict[str, Any]] = {}
    names: dict[str, str] = {}
    problems: list[str] = []
    for slot, decl in sorted(declarations.items()):
        status, probs = validate_declaration(decl, today=today)
        if decl.get("language") != language:
            probs = probs + [f"declaration is for {decl.get('language')!r}, not {language!r}"]
            status = "INCOMPLETE"
        if decl.get("rater_slot") != slot:
            probs = probs + ["rater_slot inside the declaration differs from its file"]
            status = "INCOMPLETE"
        per[slot] = {"status": status, "problems": probs}
        key = str(decl.get("reviewer_name", "")).strip().casefold()
        if key in names:
            problems.append(f"the same person appears as {names[key]} and {slot}")
        names[key] = slot
    eligible = sum(1 for v in per.values() if v["status"] == "ELIGIBLE_FOR_OWNER_APPOINTMENT")
    if len(declarations) < expected_raters:
        problems.append(f"{len(declarations)} declaration(s) for {expected_raters} rater slot(s)")
    ok = not problems and eligible == expected_raters and len(declarations) == expected_raters
    return {"ok": ok, "eligible": eligible, "needs_owner_decision": sorted(s for s, v in per.items() if v["status"] == "OWNER_DECISION_REQUIRED"), "per_rater": per, "problems": problems}


# ------------------------------------------------------------------------------------------------------------------------------------------------ analysis
def _load_ratings(packet_dir: Path, ratings_dir: Path, lang: str, key: Mapping, complete: Sequence[str]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for rater in complete:
        rows, errs = R._read_sheet(Path(ratings_dir) / lang / rater / "rating_sheet.csv")
        if errs:
            continue
        out[rater] = {r["sample_id"]: {**{d: int(r[d]) for d in DIMENSIONS}, **{f: (r[f] or "").strip().upper() for f in FLAGS}} for r in rows}
    return out


def _compare(value: float | None, minimum: float) -> str:
    return "NOT_COMPUTED" if value is None else ("AT_OR_ABOVE_PROPOSAL" if value >= minimum else "BELOW_PROPOSAL")


def analyse_language(packet_dir: Path, ratings_dir: Path, lang: str, base: Mapping[str, Any], key: Mapping, *, declarations: Mapping[str, Mapping[str, Any]] | None, fake: bool, seed: str,
                     today: date | None = None) -> dict[str, Any]:
    """One language's result record. ``base`` is the 06C aggregate entry for the language (validity, completeness, control behaviour)."""
    expected_raters = int(base["raters_expected"])
    raters = sorted(r for r in base["controls_failed_by_rater"] if r not in base["incomplete_raters"])
    data = _load_ratings(packet_dir, ratings_dir, lang, key, raters) if base["status"] in ("READY_FOR_HUMAN_REVIEW", "CONTROLS_FAILED") else {}
    graded = sorted(sid for sid, m in key.items() if m["language"] == lang and m["source"] != "control")
    model_items = sorted(sid for sid in graded if key[sid]["source"] == "model_output")
    dims: dict[str, Any] = {}
    agreement: dict[str, Any] = {}
    flags: dict[str, Any] = {}
    by_task: dict[str, dict[str, float]] = {}
    if data and len(data) >= 2:
        item_means = {d: {sid: statistics.fmean(data[r][sid][d] for r in data) for sid in graded} for d in DIMENSIONS}
        for d in DIMENSIONS:
            ci = mean_ci95(list(item_means[d].values()))
            shares = [sum(1 for r in data if data[r][sid][d] >= 4) / len(data) for sid in graded]
            lo, hi = wilson_interval95(round(sum(shares)), len(graded)) if graded else (None, None)
            dims[d] = {"n_items": ci["n"], "mean": ci["mean"], "sd": ci["sd"], "ci95_low": ci["low"], "ci95_high": ci["high"], "share_4_or_5": round(statistics.fmean(shares), 3) if shares else None,
                       "share_4_or_5_wilson95_low": lo, "share_4_or_5_wilson95_high": hi}
            units = [[data[r][sid][d] for r in sorted(data)] for sid in graded]
            lo_a, hi_a = krippendorff_ci95(units, "ordinal", seed=f"{seed}|{lang}|{d}")
            pairs = [(a, b) for i, a in enumerate(sorted(data)) for b in sorted(data)[i + 1:]]
            wk = [cohen_kappa([data[a][s][d] for s in graded], [data[b][s][d] for s in graded], weights="quadratic", categories=range(1, 6)) for a, b in pairs]
            uk = [cohen_kappa([data[a][s][d] for s in graded], [data[b][s][d] for s in graded], categories=range(1, 6)) for a, b in pairs]
            alpha = krippendorff_alpha(units, "ordinal")
            agreement[d] = {"raters": len(data), "krippendorff_alpha_ordinal": alpha, "alpha_ci95_low": lo_a, "alpha_ci95_high": hi_a, "krippendorff_alpha_nominal": krippendorff_alpha(units, "nominal"),
                            "cohen_kappa_weighted_mean": round(statistics.fmean([k for k in wk if k is not None]), 4) if any(k is not None for k in wk) else None,
                            "cohen_kappa_unweighted_mean": round(statistics.fmean([k for k in uk if k is not None]), 4) if any(k is not None for k in uk) else None,
                            "alpha_band": alpha_band(alpha)}
        for task in sorted({key[s]["task"] for s in model_items}):
            ids = [s for s in model_items if key[s]["task"] == task]
            by_task[task] = {d: round(statistics.fmean(data[r][s][d] for r in data for s in ids), 3) for d in DIMENSIONS}
        for f in FLAGS:
            k = sum(1 for sid in graded if any(data[r][sid][f] == "Y" for r in data))
            n = len(graded)
            lo, hi = wilson_interval95(k, n)
            flags[f] = {"items_flagged_by_any_rater": k, "n_items": n, "rate": round(k / n, 4), "wilson95_low": lo, "wilson95_high": hi, "upper95_if_zero": upper95_if_zero(n) if k == 0 else None}
    reviewers: dict[str, Any] = {}
    independence: dict[str, Any] | None = None
    if declarations is not None:
        independence = check_independence(declarations, lang, expected_raters, today=today)
        for slot in sorted(set(raters) | set(declarations)):
            d = declarations.get(slot)
            reviewers[slot] = {"name": (d or {}).get("reviewer_name") or NOT_NAMED, "independence": independence["per_rater"].get(slot, {}).get("status", "NO_DECLARATION")}
    else:
        reviewers = {slot: {"name": NOT_NAMED, "independence": "NO_DECLARATION"} for slot in (raters or [f"rater_R{i}" for i in range(1, expected_raters + 1)])}
    if fake:
        status = "SELFTEST_ONLY"
    elif base["status"] == "INCOMPLETE" or base["error_count"]:
        status = "INCOMPLETE"
    elif base["raters_complete"] < max(expected_raters, MIN_RATERS):
        status = "RATERS_INSUFFICIENT"
    elif base["status"] == "CONTROLS_FAILED":
        status = "CONTROLS_FAILED"
    elif independence is None:
        status = "REVIEWERS_UNVERIFIED"
    elif not independence["ok"]:
        status = "REVIEWERS_NOT_INDEPENDENT"
    else:
        status = "READY_FOR_OWNER_REVIEW"
    comparison = _proposal_comparison(dims, agreement, flags, len(model_items), len(data))
    return {"schema": RESULT_SCHEMA_ID, "protocol": PROTOCOL_VERSION, "language": lang, "fake": fake, "status": status, "approved": False, "approver": None, "approved_on": None, "release_sha": None,
            "thresholds": {"adopted": False, "source": THRESHOLDS_NOT_SET, "proposals_are_not_adopted": True},
            "sample": {"model_output_items": len(model_items), "policy_sentence_items": len(graded) - len(model_items), "control_items": int(base["controls_per_sheet"]),
                       "raters_expected": expected_raters, "raters_complete": int(base["raters_complete"]), "unit_of_analysis": "item (mean of its raters)"},
            "reviewers": reviewers, "independence": ({"ok": independence["ok"], "eligible": independence["eligible"], "needs_owner_decision": independence["needs_owner_decision"], "problems": independence["problems"]}
                                                   if independence else None),
            "dimensions": dims, "by_task": by_task, "agreement": agreement, "flags": flags, "controls": {"failed_by_rater": base["controls_failed_by_rater"], "raters_failing": base["raters_failing_controls"]},
            "proposal_comparison": comparison, "validation_errors": base["error_count"],
            "limitations": ["Rater effects are not modelled in the item-level interval.", "Reviewers rate synthetic prompts, not real conversations.", "Blinding is imperfect: the language and a typical model style are visible.",
                            "A native rating does not replace the interface and legal review (LG-10, LG-11)."]}


def _proposal_comparison(dims: Mapping, agreement: Mapping, flags: Mapping, n_model: int, n_raters: int) -> dict[str, Any]:
    p = PROPOSED_LEVELS
    out: dict[str, Any] = {"label": p["label"], "informational_only": True,
                           "sample_size": "AT_OR_ABOVE_PROPOSAL" if n_model >= p["min_items_per_language"] else "BELOW_PROPOSAL",
                           "raters": "AT_OR_ABOVE_PROPOSAL" if n_raters >= p["min_raters"] else "BELOW_PROPOSAL", "mean": {}, "ci95_lower_bound": {}, "share_4_or_5": {}, "alpha_ordinal": {}, "flag_upper95": {}}
    for d in DIMENSIONS:
        x = dims.get(d, {})
        out["mean"][d] = _compare(x.get("mean"), p["mean_rating_min"])
        out["ci95_lower_bound"][d] = _compare(x.get("ci95_low"), p["lower_95_bound_min"])
        out["share_4_or_5"][d] = _compare(x.get("share_4_or_5"), p["share_4_or_5_min"])
        out["alpha_ordinal"][d] = _compare(agreement.get(d, {}).get("krippendorff_alpha_ordinal"), p["krippendorff_alpha_ordinal_min"])
    for f, cap in (("unsafe_content", p["unsafe_content_upper95_max"]), ("wrong_language", p["wrong_language_upper95_max"])):
        hi = flags.get(f, {}).get("wilson95_high")
        out["flag_upper95"][f] = "NOT_COMPUTED" if hi is None else ("AT_OR_ABOVE_PROPOSAL" if hi <= cap else "BELOW_PROPOSAL")
    return out


def load_declarations(directory: Path | None, lang: str) -> dict[str, dict] | None:
    if directory is None:
        return None
    base = Path(directory) / lang
    if not base.is_dir():
        return None
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(base.glob("rater_R*.json"))}


def analyse(packet_dir: Path, ratings_dir: Path, *, declarations_dir: Path | None = None, today: date | None = None) -> dict[str, Any]:
    """The 06G report over a packet and the returned sheets. Never approves: ``approved`` is false and no status is a pass."""
    packet_dir = Path(packet_dir)
    summary = R.aggregate(packet_dir, ratings_dir)
    key = json.loads((packet_dir / "private" / "key.json").read_text(encoding="utf-8"))
    manifest = json.loads((packet_dir / "private" / "manifest.json").read_text(encoding="utf-8"))
    fake = bool(manifest.get("fake"))
    languages = {lang: analyse_language(packet_dir, ratings_dir, lang, summary["languages"][lang], key, declarations=load_declarations(declarations_dir, lang), fake=fake,
                                        seed=str(manifest.get("seed", "")), today=today) for lang in LANGUAGES}
    return {"schema": REPORT_SCHEMA_ID, "protocol": PROTOCOL_VERSION, "package": "06G", "gate_ids": ["PG-07", "LG-04", "LG-05"], "fake": fake,
            "status": "SELFTEST_ONLY" if fake else ("READY_FOR_OWNER_REVIEW" if all(v["status"] == "READY_FOR_OWNER_REVIEW" for v in languages.values()) else "INCOMPLETE"),
            "approved": False, "approver": None, "approved_on": None, "release_sha": None,
            "thresholds": {"adopted": False, "source": THRESHOLDS_NOT_SET, "proposals_are_not_adopted": True, "proposals": PROPOSED_LEVELS},
            "note": "Evidence for the owner and a named human approver. It approves nothing. Gate states are recorded only in docs/production/execution/language_readiness.json by a named human.",
            "languages": languages}


# ------------------------------------------------------------------------------------------------------------------------------------------------ report
_PASS_WORD = re.compile(r"\bPASS(?:ED|ES)?\b")


def assert_no_pass(text: str) -> str:
    """The report generator can NEVER emit PASS: any capitalised PASS in its output is a defect and raises."""
    if _PASS_WORD.search(text):
        raise AssertionError("a human-evaluation report must never contain PASS")
    return text


def render_report_md(report: Mapping[str, Any]) -> str:
    p = report["thresholds"]["proposals"]
    out = ["# Independent human evaluation report (06G)", "",
           f"- Overall status: **{report['status']}**" + (" (fake data: nothing here is evidence)" if report["fake"] else ""),
           f"- Approved: {report['approved']}; approver: {report['approver']}; release SHA: {report['release_sha']}",
           f"- Thresholds: {report['thresholds']['source']}", "",
           "This report states what was measured and how uncertain it is. It does not approve a gate. The comparison columns use PROPOSED levels that the owner has not adopted.", "",
           "## Per language", "", "| language | status | items | raters | clarity | correctness | tone | policy | alpha (ordinal, policy) | unsafe upper 95% | wrong-language upper 95% |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for lang, v in report["languages"].items():
        def cell(d: str) -> str:
            x = v["dimensions"].get(d)
            return "n/a" if not x or x["mean"] is None else f"{x['mean']} [{x['ci95_low']}, {x['ci95_high']}]"
        al = v["agreement"].get("policy_adherence", {}).get("krippendorff_alpha_ordinal", "n/a")
        up = v["flags"].get("unsafe_content", {}).get("wilson95_high", "n/a")
        wl = v["flags"].get("wrong_language", {}).get("wilson95_high", "n/a")
        out.append(f"| {lang} | {v['status']} | {v['sample']['model_output_items']} | {v['sample']['raters_complete']}/{v['sample']['raters_expected']} | {cell('clarity')} | {cell('correctness')} | "
                   f"{cell('tone')} | {cell('policy_adherence')} | {al} | {up} | {wl} |")
    out += ["", "Cells show the mean rating with the 95 percent interval over items. Intervals are item-level and ignore rater effects.", "",
            f"## Comparison against {p['label']}", "",
            f"Proposed levels (informational): mean at least {p['mean_rating_min']}, lower 95 percent bound at least {p['lower_95_bound_min']}, share rated 4 or 5 at least {p['share_4_or_5_min']}, "
            f"flag upper bound at most {p['unsafe_content_upper95_max']}, alpha at least {p['krippendorff_alpha_ordinal_min']}, at least {p['min_raters']} raters and {p['min_items_per_language']} items.", "",
            "| language | sample | raters | means | lower bounds | alpha | flag bounds |", "|---|---|---|---|---|---|---|"]
    for lang, v in report["languages"].items():
        c = v["proposal_comparison"]
        short = lambda m: ", ".join(f"{k[:4]}:{x.replace('_PROPOSAL', '').replace('AT_OR_ABOVE', 'at/above').replace('BELOW', 'below').lower()}" for k, x in m.items()) or "n/a"  # noqa: E731
        out.append(f"| {lang} | {c['sample_size']} | {c['raters']} | {short(c['mean'])} | {short(c['ci95_lower_bound'])} | {short(c['alpha_ordinal'])} | {short(c['flag_upper95'])} |")
    out += ["", "## Reviewers and independence", ""]
    for lang, v in report["languages"].items():
        ind = v["independence"]
        out.append(f"- {lang}: " + ("no declarations supplied (REVIEWERS_UNVERIFIED)" if ind is None else f"independent and complete: {ind['ok']}; owner decision needed for {ind['needs_owner_decision'] or 'none'}; problems: {ind['problems'] or 'none'}")
                   + "; reviewers: " + ", ".join(f"{s}={r['name']}" for s, r in v["reviewers"].items()))
    out += ["", "## Limits", ""] + [f"- {x}" for x in report["languages"][next(iter(report["languages"]))]["limitations"]] + ["", report["note"], ""]
    return assert_no_pass("\n".join(out))


# ------------------------------------------------------------------------------------------------------------------------------------------------ results schema
def _mini_schema() -> dict[str, Any]:
    num = {"type": ["number", "null"]}
    cmp_ = {"type": "string", "enum": ["AT_OR_ABOVE_PROPOSAL", "BELOW_PROPOSAL", "NOT_COMPUTED"]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": RESULT_SCHEMA_ID, "title": "06G human evaluation result for ONE language", "type": "object",
        "required": ["schema", "protocol", "language", "fake", "status", "approved", "approver", "approved_on", "release_sha", "thresholds", "sample", "reviewers", "independence", "dimensions", "by_task",
                     "agreement", "flags", "controls", "proposal_comparison", "validation_errors", "limitations"],
        "additionalProperties": False,
        "properties": {
            "schema": {"const": RESULT_SCHEMA_ID}, "protocol": {"const": PROTOCOL_VERSION}, "language": {"enum": list(LANGUAGES)}, "fake": {"type": "boolean"},
            "status": {"enum": list(STATUSES)}, "approved": {"const": False}, "approver": {"const": None}, "approved_on": {"const": None}, "release_sha": {"const": None},
            "thresholds": {"type": "object", "required": ["adopted", "source", "proposals_are_not_adopted"], "additionalProperties": False,
                           "properties": {"adopted": {"const": False}, "source": {"type": "string"}, "proposals_are_not_adopted": {"const": True}}},
            "sample": {"type": "object", "required": ["model_output_items", "policy_sentence_items", "control_items", "raters_expected", "raters_complete", "unit_of_analysis"], "additionalProperties": False,
                       "properties": {"model_output_items": {"type": "integer", "minimum": 0}, "policy_sentence_items": {"type": "integer", "minimum": 0}, "control_items": {"type": "integer", "minimum": 0},
                                      "raters_expected": {"type": "integer", "minimum": 0}, "raters_complete": {"type": "integer", "minimum": 0}, "unit_of_analysis": {"type": "string"}}},
            "reviewers": {"type": "object", "additionalProperties": {"type": "object", "required": ["name", "independence"], "additionalProperties": False,
                                                                       "properties": {"name": {"type": "string"}, "independence": {"type": "string"}}}},
            "independence": {"type": ["object", "null"]},
            "dimensions": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": num}},
            "by_task": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": {"type": "number"}}},
            "agreement": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": {"type": ["number", "integer", "string", "null"]}}},
            "flags": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": num}},
            "controls": {"type": "object"}, "validation_errors": {"type": "integer", "minimum": 0}, "limitations": {"type": "array", "items": {"type": "string"}},
            "proposal_comparison": {"type": "object", "required": ["label", "informational_only", "sample_size", "raters", "mean", "ci95_lower_bound", "share_4_or_5", "alpha_ordinal", "flag_upper95"],
                                    "additionalProperties": False,
                                    "properties": {"label": {"type": "string"}, "informational_only": {"const": True}, "sample_size": cmp_, "raters": cmp_,
                                                   **{k: {"type": "object", "additionalProperties": cmp_} for k in ("mean", "ci95_lower_bound", "share_4_or_5", "alpha_ordinal", "flag_upper95")}}},
        }}


RESULT_SCHEMA = _mini_schema()


def schema_text() -> str:
    return json.dumps(RESULT_SCHEMA, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _type_ok(value: Any, t: str) -> bool:
    return {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str), "boolean": isinstance(value, bool), "null": value is None,
            "integer": isinstance(value, int) and not isinstance(value, bool), "number": isinstance(value, (int, float)) and not isinstance(value, bool)}[t]


def validate_against(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """A small validator for the subset of JSON Schema the results schema uses (type, const, enum, required, properties, additionalProperties, items, minimum)."""
    errs: list[str] = []
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        return [f"{path}: must be {schema['const']!r}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: {value!r} is not one of {schema['enum']}"]
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return [f"{path}: wrong type"]
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema and value < schema["minimum"]:
        errs.append(f"{path}: below minimum")
    if isinstance(value, dict):
        for r in schema.get("required", []):
            if r not in value:
                errs.append(f"{path}: missing {r!r}")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                errs += validate_against(v, props[k], f"{path}.{k}")
            elif addl is False:
                errs.append(f"{path}: unexpected {k!r}")
            elif isinstance(addl, dict):
                errs += validate_against(v, addl, f"{path}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            errs += validate_against(v, schema["items"], f"{path}[{i}]")
    return errs


def validate_result(record: Mapping[str, Any]) -> list[str]:
    """Problems with one language's result record (schema, plus: no status may contain PASS)."""
    errs = validate_against(record, RESULT_SCHEMA)
    if _PASS_WORD.search(json.dumps(record, ensure_ascii=False)):
        errs.append("$: the record contains PASS")
    return errs


# ------------------------------------------------------------------------------------------------------------------------------------------------ fake data (self-test only)
def fake_correlated_ratings(packet_dir: Path, ratings_dir: Path, *, seed: str = "selftest") -> None:
    """FAKE ratings with a shared item quality plus rater noise, so agreement statistics are exercised on data with real structure. Controls are rated as a careful reviewer would."""
    key = json.loads((Path(packet_dir) / "private" / "key.json").read_text(encoding="utf-8"))
    latent = {sid: random.Random(f"{seed}|latent|{sid}").choice((3, 4, 4, 5, 5)) for sid in key}
    for sheet in sorted((Path(packet_dir) / "reviewer").rglob("rating_sheet.csv")):
        rel = sheet.relative_to(Path(packet_dir) / "reviewer")
        rng = random.Random(f"{seed}|{rel.as_posix()}")
        with sheet.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            meta = key[row["sample_id"]]
            if meta["source"] == "control":
                exp = json.loads(meta["expectation"])
                for dim in DIMENSIONS:
                    c = exp["expect"].get(dim, {})
                    row[dim] = str(c["min"] if "min" in c else c["max"] if "max" in c else 4)
                for flag in FLAGS:
                    row[flag] = exp["flags"].get(flag, "N")
            else:
                for dim in DIMENSIONS:
                    row[dim] = str(min(5, max(1, latent[row["sample_id"]] + rng.choice((-1, 0, 0, 0, 1)))))
                row["wrong_language"], row["unsafe_content"] = "N", "N"
        target = Path(ratings_dir) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(R.SHEET_COLUMNS))
            w.writeheader()
            w.writerows(rows)


def fake_declarations(directory: Path, raters: int = MIN_RATERS, *, today: date | None = None) -> None:
    """FAKE completed declarations with obviously synthetic labels (self-test only; written into a temp directory)."""
    when = (today or datetime.now(timezone.utc).date()).isoformat()
    for lang in LANGUAGES:
        for r in range(1, raters + 1):
            name = f"Selftest Reviewer {lang.upper()}{r}"
            d = declaration_template(lang, f"rater_R{r}")
            d.update({"reviewer_name": name, "native_or_fluent_statement": "SELFTEST: synthetic declaration, not a person.", "relationships_to_owner_or_product": "NONE", "other_conflicts": "NONE",
                      "declaration_date": when, "typed_signature": name, **DECLARATION_BOOLEANS})
            path = Path(directory) / lang / f"rater_R{r}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def packet_digest(packet_dir: Path) -> str:
    """Digest of the reviewer-facing sheets (identifies exactly what reviewers were given)."""
    h = hashlib.sha256()
    for f in R.reviewer_files(packet_dir):
        h.update(f.encode())
        h.update((Path(packet_dir) / "reviewer" / f).read_bytes())
    return h.hexdigest()
