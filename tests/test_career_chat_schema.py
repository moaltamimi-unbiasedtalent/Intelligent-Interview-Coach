"""Regression: CareerChatResponse.from_orchestration must accept the domain's numeric
authority_level (KnowledgeEvidence.authority_level is int, ge=1 le=3).

Pilot 2 defect: SourceOut.authority_level was declared `str | None`, so mapping an int
authority_level raised a Pydantic ValidationError and 500'd /career/chat whenever retrieval
returned grounded evidence — surfaced in the browser as a generic "couldn't connect" error.
This test would have caught it: it maps evidence carrying an int authority_level and asserts
the response builds and preserves the int.
"""
from types import SimpleNamespace

from src.api.schemas.career import CareerChatResponse, SourceOut


def _evidence(authority_level):
    return SimpleNamespace(
        source_title="O*NET: Registered Nurses",
        source_url="https://www.onetonline.org/link/summary/29-1141.00",
        evidence_type="occupation_description",
        authority_level=authority_level,  # domain provides an int tier (1..3)
        geography="US",
        occupation_title="Registered Nurses",
        reference_year=2025,
    )


def _result(evidence):
    response = SimpleNamespace(
        answer="Here are the key skills for a registered nurse.",
        citations=[],
        evidence=evidence,
        tool_calls=[],
    )
    return SimpleNamespace(response=response, trace=SimpleNamespace(), preparation_artifacts=None)


def test_source_out_accepts_int_authority_level():
    # Direct schema guard: an int tier must validate (matches the domain model).
    s = SourceOut(authority_level=1)
    assert s.authority_level == 1


def test_from_orchestration_maps_int_authority_level_without_error():
    # The real seam that 500'd in Pilot 2: grounded evidence with a numeric authority tier.
    out = CareerChatResponse.from_orchestration(_result([_evidence(1)]))
    assert len(out.sources) == 1
    assert out.sources[0].authority_level == 1
    assert out.sources[0].occupation_title == "Registered Nurses"
    assert out.has_evidence is True


def test_from_orchestration_handles_all_authority_tiers():
    out = CareerChatResponse.from_orchestration(
        _result([_evidence(1), _evidence(2), _evidence(3)])
    )
    assert [s.authority_level for s in out.sources] == [1, 2, 3]
