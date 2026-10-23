"""Candidate retrieval approval filter (02D): an unqualified source is not retrievable.

Applied once, in the shared evidence-gathering stage of the Career service (so ``/career/chat`` and Mo's ``SearchCareerKnowledge`` both pass through it),
to BOTH channels a Candidate can receive knowledge from: narrative chunks (the curated corpus and Admin-governed knowledge) and structured evidence
(roles, compensation, labour market, credentials). The rule lives in :mod:`src.knowledge_approval`; this module only applies it to evidence.

* hosted environments (enforced): evidence from a source with no complete, current approval record for the Candidate's market is DROPPED, never replaced;
  evidence whose source cannot be identified is dropped too (fail closed). When nothing remains the existing abstention path reports insufficient evidence.
* development and test (labelled): nothing is dropped; every unqualified item carries ``source_qualification=UNQUALIFIED`` in its metadata (evidence text is NOT
  altered, so evaluators measure unchanged text) and the trace note names the sources.
* the market is the Candidate's selected career geography, else the country the question names (never the interface or conversation language).
  No known market means no source is enabled (fail closed).
* US-published content for a non-US market is refused while OD-US-CONTENT is undecided (see :func:`src.knowledge_approval.decide`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src import knowledge_approval as ka


@dataclass
class FilterReport:
    """What the filter did, counts and source ids only (never evidence text)."""

    market: str | None
    enforced: bool
    dropped_sources: list[str] = field(default_factory=list)
    labelled_sources: list[str] = field(default_factory=list)
    dropped_count: int = 0
    labelled_count: int = 0

    def note(self) -> str | None:
        if self.dropped_count:
            return (f"Withheld {self.dropped_count} item(s) from source(s) not qualified for market {self.market or 'unknown'}: "
                    f"{', '.join(sorted(set(self.dropped_sources)))}.")
        if self.labelled_count:
            return (f"Development only: {self.labelled_count} item(s) from source(s) not qualified for market {self.market or 'unknown'} are labelled UNQUALIFIED: "
                    f"{', '.join(sorted(set(self.labelled_sources)))}.")
        return None


def effective_market(selected: str | None, detected_country: str | None) -> str | None:
    """The Candidate's market: the selected geography, else the country the question names. Language never contributes."""
    return ka.normalise_market(selected) or ka.normalise_market(detected_country)


def _publisher_countries() -> dict[str, str]:
    try:
        from src.copilot.knowledge import manifest as km

        return {e.source_id: (e.country or "") for e in km.load_manifest()}
    except Exception:  # noqa: BLE001 - manifest unreadable: the decision then relies on the register alone
        return {}


def _decide(register: ka.Register, key: str | None, market: str | None, countries: dict[str, str]) -> ka.Decision:
    return ka.decide(register, key, market, source_country=countries.get(key or "", ""))


def filter_results(results: list, market: str | None, report: FilterReport, *, register: ka.Register | None = None) -> list:
    """Filter narrative ``RetrievalResult`` items by their chunk metadata."""
    reg = register or ka.current()
    countries = _publisher_countries()
    kept = []
    for r in results:
        meta = getattr(getattr(r, "chunk", None), "metadata", None)
        meta = meta if isinstance(meta, dict) else (getattr(r, "metadata", None) or {})
        key = ka.source_key(meta)
        d = _decide(reg, key, market, countries)
        if not d.allowed:
            report.dropped_count += 1
            report.dropped_sources.append(key or "unidentified")
            continue
        if d.labelled_unqualified:
            report.labelled_count += 1
            report.labelled_sources.append(key or "unidentified")
            _label_chunk(r)
        elif d.general_information:
            _label_chunk(r, general=True)
        kept.append(r)
    return kept


def filter_evidence(evidence: list, market: str | None, report: FilterReport, *, register: ka.Register | None = None) -> list:
    """Filter structured ``KnowledgeEvidence`` items by their source id."""
    reg = register or ka.current()
    countries = _publisher_countries()
    kept = []
    for e in evidence:
        key = ka.source_key(getattr(e, "metadata", None), getattr(e, "source_id", None))
        d = _decide(reg, key, market, countries)
        if not d.allowed:
            report.dropped_count += 1
            report.dropped_sources.append(key or "unidentified")
            continue
        if d.labelled_unqualified:
            report.labelled_count += 1
            report.labelled_sources.append(key or "unidentified")
            e.metadata = {**(e.metadata or {}), "source_qualification": "UNQUALIFIED"}
        elif d.general_information:
            e.metadata = {**(e.metadata or {}), "source_qualification": "NON_EU_GENERAL_INFORMATION", "source_qualification_label": ka.US_GENERAL_INFORMATION_LABEL}
        kept.append(e)
    return kept


def _label_chunk(result: Any, *, general: bool = False) -> None:
    chunk = result.chunk
    chunk.metadata = ({**(chunk.metadata or {}), "source_qualification": "NON_EU_GENERAL_INFORMATION", "source_qualification_label": ka.US_GENERAL_INFORMATION_LABEL}
                      if general else {**(chunk.metadata or {}), "source_qualification": "UNQUALIFIED"})


def apply(results: list, structured: list, *, selected_market: str | None, detected_country: str | None,
          register: ka.Register | None = None) -> tuple[list, list, FilterReport]:
    """Filter both channels. Returns ``(results, structured_evidence, report)``."""
    reg = register or ka.current()
    market = effective_market(selected_market, detected_country)
    report = FilterReport(market=market, enforced=reg.enforced)
    return (filter_results(list(results), market, report, register=reg),
            filter_evidence(list(structured), market, report, register=reg), report)
