"""Append-only human-review trail for Feedback Intelligence recommendations (Phase 7G, §35/§73).

A ReviewDecision (approve / reject / defer) is appended to an immutable JSONL log inside the run
directory. APPROVE means "approved for an engineer to consider" — it NEVER executes, modifies
production, runs code, or touches Git (§36). History is append-only; a new decision never rewrites
a prior one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.copilot.feedback_intelligence.guards import safe_output_path
from src.copilot.feedback_intelligence.models import ReviewDecision, ReviewOutcome

_LOG = "review_decisions.jsonl"


def record_decision(run_dir: str | Path, proposal_id: str, decision: str,
                    *, reviewer_id: str | None = None, reason: str | None = None) -> ReviewDecision:
    """Append one review decision. Returns the recorded decision (``executed`` is always False)."""
    outcome = ReviewOutcome(decision.strip().lower())
    rec = ReviewDecision(
        proposal_id=proposal_id, decision=outcome,
        reviewed_at=datetime.now(timezone.utc), reviewer_id=reviewer_id,
        reason=reason, executed=False)  # approval NEVER executes anything (§36)
    path = safe_output_path(Path(run_dir) / _LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:  # append-only (§74)
        fh.write(rec.model_dump_json() + "\n")
    return rec


def load_decisions(run_dir: str | Path) -> list[ReviewDecision]:
    path = Path(run_dir) / _LOG
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(ReviewDecision.model_validate_json(line))
    return out
