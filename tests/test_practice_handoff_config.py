"""Regression: Career → Practice handoff configuration must be reliable.

The bug: after an approved practice handoff, ``POST /api/v1/interviews`` with a
``preparation_context`` could fail with an opaque 422 even when the candidate supplied
a valid industry/sector and career level. Two causes:

1. A VALID PreparationContext (job description up to 12k, composed background up to 6k)
   overflowed the Interview domain's ``InterviewConfiguration`` limits (JD 8k, background
   4k) → a generic ``validation_error`` 422 the UI mistook for "missing config".
2. The genuinely-missing-config case shared that generic code, so the UI could not tell
   the two apart.

These tests pin the fixed contract:

* the Interview-bound projection is BOUNDED to the Interview limits (no overflow);
* the genuinely-missing case raises the dedicated ``MissingHandoffConfigError`` with the
  stable ``missing_interview_handoff_config`` code;
* a supplied valid gap-filler (Fashion / executive) completes the configuration;
* an already-present context value is preserved.

Both a unit level (``_build_configuration``) and an HTTP level (fake services, no
provider calls) are covered.
"""

from __future__ import annotations

import pytest

from src import constants
import src.api.routes.interview as interview_route
from src.api.schemas.interview import CreateInterviewRequest, PreparationContextIn
from src.application.errors import MissingHandoffConfigError, ValidationError
from src.integration import handoff
from src.integration.models import PreparationContext


def _body(pc: PreparationContext, **extra) -> CreateInterviewRequest:
    return CreateInterviewRequest(
        preparation_context=PreparationContextIn(**pc.model_dump()), **extra
    )


# --- unit: _build_configuration ---------------------------------------------


def test_valid_context_builds_configuration():
    pc = PreparationContext(target_role="PM", industry="Fashion", seniority="executive")
    cfg = interview_route._build_configuration(_body(pc))
    assert cfg.industry_or_sector == "Fashion"
    assert cfg.career_level == "executive"


def test_missing_industry_raises_dedicated_error():
    # No industry and no seniority-derived level, nothing supplied.
    pc = PreparationContext(target_role="PM")
    with pytest.raises(MissingHandoffConfigError):
        interview_route._build_configuration(_body(pc))


def test_missing_career_level_raises_dedicated_error():
    # Industry present, but no seniority and no supplied career level.
    pc = PreparationContext(target_role="PM", industry="Fashion")
    with pytest.raises(MissingHandoffConfigError):
        interview_route._build_configuration(_body(pc))


def test_supplied_gap_fillers_complete_configuration():
    # The reported case: context lacks both; the candidate supplies Fashion + executive.
    pc = PreparationContext(target_role="PM")
    cfg = interview_route._build_configuration(
        _body(pc, industry_or_sector="Fashion", career_level="executive")
    )
    assert cfg.industry_or_sector == "Fashion"
    assert cfg.career_level == "executive"


def test_executive_is_a_valid_career_level():
    assert "executive" in constants.CAREER_LEVELS


def test_context_value_wins_over_supplied_when_present():
    # A valid context value is preserved; the override only fills a genuine gap.
    pc = PreparationContext(target_role="PM", industry="Healthcare", seniority="senior")
    cfg = interview_route._build_configuration(
        _body(pc, industry_or_sector="Fashion", career_level="executive")
    )
    assert cfg.industry_or_sector == "Healthcare"
    assert cfg.career_level == "senior"


def test_long_job_description_is_bounded_not_rejected():
    # Valid in PreparationContext (>8k, <=12k) — historically invalid for the interview.
    long_jd = "x" * 10_000
    pc = PreparationContext(
        target_role="PM", industry="Fashion", seniority="executive", job_description=long_jd
    )
    cfg = interview_route._build_configuration(_body(pc))
    assert len(cfg.job_description) == constants.MAX_JOB_DESCRIPTION_CHARS


def test_large_composed_background_is_bounded_not_rejected():
    pc = PreparationContext(
        target_role="PM",
        industry="Fashion",
        seniority="executive",
        candidate_strengths=["S" * 380] * 15,  # composes to > 4k before bounding
    )
    assert len(handoff._compose_background(pc)) == constants.MAX_CANDIDATE_BACKGROUND_CHARS
    cfg = interview_route._build_configuration(_body(pc))
    assert len(cfg.candidate_background) <= constants.MAX_CANDIDATE_BACKGROUND_CHARS


def test_invalid_career_level_is_generic_validation_not_missing_config():
    # A value outside the taxonomy is a generic (safe) validation error, NOT the
    # dedicated missing-config case — so the UI won't reopen the completion form for it.
    pc = PreparationContext(target_role="PM", industry="Fashion")
    with pytest.raises(ValidationError) as exc:
        interview_route._build_configuration(_body(pc, career_level="wizard"))
    assert not isinstance(exc.value, MissingHandoffConfigError)


# --- HTTP: POST /api/v1/interviews ------------------------------------------


@pytest.fixture
def client(tmp_path):
    from tests.test_interview_api_durable import _client, _store_over
    from tests.test_api import _FakeRepo

    return _client(_store_over(f"sqlite:///{tmp_path/'iv.db'}"), _FakeRepo())


ALICE = {"X-User-Subject": "alice"}


def test_http_missing_config_returns_stable_code(client):
    with client as c:
        r = c.post(
            "/api/v1/interviews",
            json={"preparation_context": {"target_role": "PM"}},
            headers=ALICE,
        )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "missing_interview_handoff_config"


def test_http_fashion_executive_completes(client):
    with client as c:
        r = c.post(
            "/api/v1/interviews",
            json={
                "preparation_context": {"target_role": "PM"},
                "industry_or_sector": "Fashion",
                "career_level": "executive",
            },
            headers=ALICE,
        )
    assert r.status_code == 200, r.text
    assert r.json()["session_id"]


def test_http_long_jd_context_completes(client):
    with client as c:
        r = c.post(
            "/api/v1/interviews",
            json={
                "preparation_context": {
                    "target_role": "PM",
                    "industry": "Fashion",
                    "seniority": "executive",
                    "job_description": "x" * 10_000,
                }
            },
            headers=ALICE,
        )
    assert r.status_code == 200, r.text
    assert r.json()["session_id"]
