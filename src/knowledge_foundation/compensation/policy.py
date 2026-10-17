"""Governed, versionable source-precedence and evidence-class policy (GKB-5). The structure replaces any expanding set of country-specific hard-coded overrides: a policy file lists
ordered tiers (registry precedence categories) and the evidence classes each tier may produce; it is validated on load and its version travels with every resolution. Precedence only
ORDERS evidence that already matches the request on occupation, geography, reference period, pay basis, measure and source eligibility; it can never override missing or incompatible
evidence. C4 (insufficient evidence) is the absence of qualifying evidence and always means abstention, never an estimate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.knowledge_foundation import enums as E

__all__ = ["PolicyError", "PrecedencePolicy", "classify_evidence", "normalize_country", "POLICY_PATH"]

POLICY_PATH = Path(__file__).resolve().parent.parent / "data" / "compensation_precedence_policy.json"
_COUNTRY_ALIASES = {"UK": "GB", "EL": "GR"}


class PolicyError(ValueError):
    pass


def normalize_country(code: str | None) -> str | None:
    """Explicit country codes only. ``UK`` (the V1 label) maps to ``GB`` and Eurostat's ``EL`` to ``GR``; nothing is ever inferred from a language."""
    if code is None or not str(code).strip():
        return None
    c = str(code).strip().upper()
    return _COUNTRY_ALIASES.get(c, c)


@dataclass(frozen=True)
class PrecedencePolicy:
    version: str
    tiers: tuple[dict[str, Any], ...]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path = POLICY_PATH) -> "PrecedencePolicy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        pol = cls(raw["version"], tuple(raw["tiers"]), raw)
        pol.validate()
        return pol

    def validate(self) -> None:
        ranks = [t["rank"] for t in self.tiers]
        cats = [t["category"] for t in self.tiers]
        if ranks != sorted(set(ranks)) or ranks != list(range(1, len(ranks) + 1)):
            raise PolicyError("tier ranks must be contiguous and ordered")
        if len(set(cats)) != len(cats) or any(c not in E.PRECEDENCE or c == "unknown" for c in cats):
            raise PolicyError("tiers must be distinct, known registry precedence categories")
        if set(cats) != {c for c in E.PRECEDENCE if c != "unknown"}:
            raise PolicyError("every registry precedence category needs a tier")
        if any(c not in E.EVIDENCE_CLASSES for t in self.tiers for c in t["evidence_classes"]):
            raise PolicyError("unknown evidence class")
        if self.tiers[-1]["category"] != "insufficient_evidence" or self.tiers[-1]["evidence_classes"]:
            raise PolicyError("the last tier is insufficient evidence and yields no class")
        if not str(self.raw.get("country_overrides", "")).startswith("none"):
            raise PolicyError("country-specific overrides are not permitted")
        if "overrides" in self.raw or any(k.upper() in {"DE", "US", "UK", "GB", "EU"} for k in self.raw):
            raise PolicyError("country-specific keys are not permitted")

    def rank(self, category: str | None) -> int | None:
        for t in self.tiers:
            if t["category"] == category:
                return t["rank"]
        return None

    def classes_for(self, category: str | None) -> tuple[str, ...]:
        for t in self.tiers:
            if t["category"] == category:
                return tuple(t["evidence_classes"])
        return ()

    def presentable(self, category: str | None, evidence_class: str | None) -> bool:
        return evidence_class in self.classes_for(category)


def classify_evidence(policy: PrecedencePolicy, precedence_category: str | None, occupation_level: str, geography_level: str) -> str | None:
    """Evidence class from the ACTUAL specificity of the source: C1 national detailed, C2 national broad, C3 international harmonised (a regional figure from a national tier keeps its class and is labelled regional; it is only returned when that region is requested). A broad statistical source is never classed as
    occupation-specific because its country matches. Returns None when no class applies (the importer then rejects the row)."""
    allowed = policy.classes_for(precedence_category)
    if precedence_category in ("national_official_occupation_statistics", "national_public_employment_service"):
        # Policy p10c-d/1: a subnational figure from a national source is classed by OCCUPATION specificity (the class describes the source) and is labelled regional by the resolver.
        if geography_level not in ("national", "regional"):
            return None
        cls = {"detailed": "C1", "broad": "C2"}.get(occupation_level)
    elif precedence_category == "eurostat_harmonised":
        cls = "C3" if geography_level in ("national", "eu_aggregate") and occupation_level in ("detailed", "broad") else None
    else:
        cls = None
    return cls if cls in allowed else None
