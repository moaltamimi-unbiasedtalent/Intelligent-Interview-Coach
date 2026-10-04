"""The APPROVED model catalogue (P10B-W10.7). Code-defined: an administrator picks an entry by id, never types a provider slug.

Entries mirror the models that already exist in the typed registry (``src/llm/models.py``); this wave adds no model and no provider. The
slug of an entry is the registry's code default for its tier, so no catalogue slug is ever user-supplied input. Capability flags are the
registry's conservative declarations. ``cost_class`` is a relative ordinal (1 lowest), not a price: Ask4Mo holds no model price here.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.llm.models import ModelProfile, default_slug, spec

CATALOGUE_VERSION = "2026-10-04.1"
TIER_RANK = {ModelProfile.FAST: 0, ModelProfile.BALANCED: 1, ModelProfile.ADVANCED: 2}


@dataclass(frozen=True)
class CatalogueEntry:
    id: str
    display_name: str
    tier: ModelProfile
    allowed_profiles: tuple[ModelProfile, ...]
    cost_class: int
    note: str

    @property
    def slug(self) -> str:
        return default_slug(self.tier)

    @property
    def supports_tools(self) -> bool:
        return spec(self.tier).supports_tools

    @property
    def supports_structured_output(self) -> bool:
        return spec(self.tier).supports_structured_output

    @property
    def supports_temperature(self) -> bool:
        return spec(self.tier).supports_temperature


_F, _B, _A = ModelProfile.FAST, ModelProfile.BALANCED, ModelProfile.ADVANCED

CATALOGUE: dict[str, CatalogueEntry] = {
    "luna": CatalogueEntry("luna", "Luna (Fast tier)", _F, (_F, _B), 1, "Lower-cost bounded tasks; may serve Fast or Balanced."),
    "terra": CatalogueEntry("terra", "Terra (Balanced tier)", _B, (_F, _B, _A), 2, "Default workhorse; may serve any profile."),
    "sol": CatalogueEntry("sol", "Sol (Advanced tier)", _A, (_B, _A), 3, "Highest capability; may serve Balanced or Advanced."),
}

# What the code ships today: the baseline every configuration is compared with and the target of "revert to code".
BASELINE_PROFILES: dict[str, str] = {_F.value: "luna", _B.value: "terra", _A.value: "sol"}


def catalogue_ids() -> tuple[str, ...]:
    return tuple(CATALOGUE)


def slug_for(entry_id: str) -> str:
    return CATALOGUE[entry_id].slug
