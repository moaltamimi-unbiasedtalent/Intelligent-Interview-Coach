"""Treat retrieved chunks as untrusted source material.

Retrieved text is data, never instructions. Each chunk is scanned for embedded
injection: a blocked chunk (imperative attack text) is **excluded** from the
evidence; a warned chunk is kept but marked. If enough valid evidence remains the
pipeline continues on the safe subset.

01A (REVIEW-01 R5/R6): every screened chunk also carries an ``injection_risk`` score (0.0 to 1.0) plus the matched indicator NAMES (never raw text). A chunk whose
risk is above ``constants.INJECTION_QUARANTINE_RISK`` is quarantined: excluded before any model context is built. The score is the existing scanner score over the
block threshold, so no detector weight is duplicated or changed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.copilot import constants
from src.copilot.models import RetrievalResult
from src.copilot.security.injection import InjectionScan, scan_text

__all__ = ["ScreenResult", "screen_results", "injection_risk_from_scan"]


@dataclass
class ScreenResult:
    """Outcome of screening retrieved results for injection."""

    kept: list[RetrievalResult] = field(default_factory=list)
    excluded: list[tuple[RetrievalResult, InjectionScan]] = field(default_factory=list)
    warned: list[tuple[RetrievalResult, InjectionScan]] = field(default_factory=list)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded)

    @property
    def quarantined_count(self) -> int:
        """Chunks withheld from the model context because their injection risk was above the quarantine threshold."""
        return len(self.excluded)

    @property
    def max_risk(self) -> float:
        """Highest injection risk seen across all screened chunks (0.0 when none was suspicious)."""
        risks = [r.injection_risk for r in self.kept] + [r.injection_risk for r, _ in self.excluded]
        return max(risks, default=0.0)

    def summary(self) -> str | None:
        if not self.excluded and not self.warned:
            return None
        parts = []
        if self.excluded:
            parts.append(f"excluded {len(self.excluded)} chunk(s) with embedded instructions")
        if self.warned:
            parts.append(f"flagged {len(self.warned)} suspicious chunk(s)")
        return "Retrieved-content guard: " + ", ".join(parts) + "."


def injection_risk_from_scan(scan: InjectionScan) -> float:
    """Map a scanner score onto 0.0-1.0: the block threshold is 1.0, so a single high-weight indicator is block-level and a warn-level hit is about 0.67."""
    return round(min(1.0, max(0.0, scan.score) / constants.INJECTION_BLOCK_THRESHOLD), 4)


def screen_results(results: list[RetrievalResult], *, quarantine_risk: float | None = None) -> ScreenResult:
    """Score every retrieved chunk, quarantine those above the risk threshold and mark warnings.

    Kept results are COPIES carrying ``injection_risk`` and ``injection_indicators`` (the input objects are not mutated: they may be shared with caches). The
    threshold defaults to ``constants.INJECTION_QUARANTINE_RISK`` and can be passed explicitly for tests and evaluation.
    """
    threshold = constants.INJECTION_QUARANTINE_RISK if quarantine_risk is None else quarantine_risk
    screen = ScreenResult()
    for result in results:
        scan = scan_text(result.chunk.text)
        risk = injection_risk_from_scan(scan)
        scored = result.model_copy(update={"injection_risk": risk, "injection_indicators": list(scan.indicators)})
        if risk > threshold:
            screen.excluded.append((scored, scan))
            continue  # quarantined: never reaches the model context
        if scan.flagged:
            screen.warned.append((scored, scan))
        screen.kept.append(scored)
    return screen
