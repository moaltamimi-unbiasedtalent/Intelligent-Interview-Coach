"""Vocabulary of the knowledge foundation. The authoritative lists live next to the ORM models (so the database CHECK constraints and the code cannot drift)."""

from __future__ import annotations

from src.persistence import (COVERAGE_GROUPS, COVERAGE_LEVELS, KS_APPROVAL_STATES, KS_EVIDENCE_CLASSES, KS_LICENCE_STATUSES, KS_ORIGINS, KS_PRECEDENCE, KS_TRI_STATES,
                             KS_VALIDATION, MAPPING_STATUSES, QUALIFICATION_STATUSES, REL_BASES, REL_TYPES, TAXONOMY_ACQUISITION, TAXONOMY_SCHEMES, TAXONOMY_STATUSES)

__all__ = ["APPROVAL_STATES", "LICENCE_STATUSES", "TRI_STATES", "ORIGINS", "PRECEDENCE", "VALIDATION", "EVIDENCE_CLASSES", "SCHEMES", "TAXONOMY_STATUSES_", "ACQUISITION",
           "REL_TYPES_", "REL_BASES_", "MAPPING_STATUSES_", "QUALIFICATION_", "COVERAGE_LEVELS_", "COVERAGE_GROUPS_", "level_rank", "weakest_level", "FIXTURE_ORIGINS", "EVIDENCE_ORIGINS"]

APPROVAL_STATES = KS_APPROVAL_STATES
LICENCE_STATUSES = KS_LICENCE_STATUSES
TRI_STATES = KS_TRI_STATES
ORIGINS = KS_ORIGINS
PRECEDENCE = KS_PRECEDENCE
VALIDATION = KS_VALIDATION
EVIDENCE_CLASSES = KS_EVIDENCE_CLASSES
SCHEMES = TAXONOMY_SCHEMES
TAXONOMY_STATUSES_ = TAXONOMY_STATUSES
ACQUISITION = TAXONOMY_ACQUISITION
REL_TYPES_ = REL_TYPES
REL_BASES_ = REL_BASES
MAPPING_STATUSES_ = MAPPING_STATUSES
QUALIFICATION_ = QUALIFICATION_STATUSES
COVERAGE_LEVELS_ = COVERAGE_LEVELS
COVERAGE_GROUPS_ = COVERAGE_GROUPS

FIXTURE_ORIGINS = frozenset({"synthetic_fixture"})
# Origins that can ever be evidence (still gated by the approval lifecycle): synthetic fixtures and unknown origins can never qualify.
EVIDENCE_ORIGINS = frozenset({"official_local", "official_api", "authorized_api", "authorised_manual"})


def level_rank(level: str) -> int:
    """Ordering unsupported < targeted < source_identified < data_available < implemented < qualified. An unknown value ranks below everything (never promoted)."""
    return COVERAGE_LEVELS.index(level) if level in COVERAGE_LEVELS else -1


def weakest_level(*levels: str) -> str:
    """The weakest-link level across dimensions: coverage is only as good as its weakest dimension, never the best one."""
    if not levels:
        raise ValueError("no levels")
    return min(levels, key=level_rank)
