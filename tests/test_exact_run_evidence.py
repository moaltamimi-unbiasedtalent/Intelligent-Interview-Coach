"""Offline schema, provenance and output regressions for the 08A0 intake."""
from __future__ import annotations

import hashlib
import json
import socket

import pytest

from scripts.production import exact_run_evidence as intake

RELEASE = "1" * 40
FEATURE = "2" * 40
WRAPPER = "3" * 40


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("offline intake attempted network access")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def run(**overrides):
    return {
        "source_repository": intake.REPO,
        "source_sha": RELEASE,
        "workflow_repository": intake.REPO,
        "workflow_path": ".github/workflows/immutable-release.yml",
        "workflow_head_sha": RELEASE,
        "head_branch": "main",
        "event": "push",
        "run_id": 1001,
        "attempt": 1,
        "environment": "github_hosted_ci",
        "classification": "main_push",
        "status": "completed",
        "conclusion": "success",
        "producer": "reviewed-ci",
        "observed_on": "2026-11-06",
        "stages": [],
        "artifacts": [],
        **overrides,
    }


def pr(**overrides):
    return run(**{
        "source_sha": FEATURE, "workflow_head_sha": FEATURE, "head_branch": "feat/example",
        "event": "pull_request", "classification": "pr_head", "run_id": 1002, **overrides,
    })


def wrapper(**overrides):
    return run(**{
        "workflow_repository": intake.PRIVATE_WRAPPER_REPO, "workflow_head_sha": WRAPPER,
        "head_branch": "validation/example", "classification": "private_wrapper",
        "environment": "disposable_linux_amd64", "run_id": 1003, **overrides,
    })


def stage(identifier, outcome, *, kind="step", failure_category=None):
    return {"kind": kind, "id": identifier, "outcome": outcome, "failure_category": failure_category}


def artifact(record, content=b"synthetic archive bytes", **overrides):
    return {
        "workflow_repository": record["workflow_repository"], "run_id": record["run_id"],
        "attempt": record["attempt"], "id": 2001, "name": "local-release-metadata",
        "sha256": hashlib.sha256(content).hexdigest(), **overrides,
    }


def document(*records):
    return {"schema": intake.SCHEMA, "records": list(records)}


def validate(*records, **options):
    return intake.validate_intake(document(*records), **{"release_sha": RELEASE, **options})["observations"]


def test_main_pr_and_private_source_claims_stay_distinct():
    rows = validate(wrapper(), pr(), run())
    assert [r["classification"] for r in rows] == ["main_push", "pr_head", "private_wrapper"]
    main, feature, private = rows
    assert main["source_sha"] == main["workflow_head_sha"] == RELEASE
    assert feature["source_sha"] == feature["workflow_head_sha"] == FEATURE
    assert private["source_sha"] == RELEASE and private["workflow_head_sha"] == WRAPPER
    assert {r["conclusion"] for r in rows} == {"success"}


def test_manual_dispatch_at_release_sha_retains_its_separate_event():
    observed, = validate(run(classification="manual_dispatch", event="workflow_dispatch"))
    assert observed["classification"] == "manual_dispatch"


@pytest.mark.parametrize(("changes", "problem"), [
    ({"source_sha": "abc1234"}, "complete Git SHAs"),
    ({"workflow_head_sha": "0" * 40}, "complete Git SHAs"),
    ({"workflow_head_sha": FEATURE}, "does not match workflow head"),
    ({"source_sha": FEATURE, "workflow_head_sha": FEATURE}, "explicit release SHA"),
    ({"head_branch": "feature/release"}, "main branch"),
    ({"event": "pull_request"}, "conflicts with classification"),
    ({"event": "schedule"}, "conflicts with classification"),
    ({"workflow_repository": intake.PRIVATE_WRAPPER_REPO}, "conflicts with classification"),
    ({"source_repository": "other/project"}, "unexpected source repository"),
    ({"workflow_path": "https://example.test/check.yml"}, "invalid workflow path"),
    ({"workflow_path": ".github/workflows/e2e.yml"}, "unsupported main push workflow"),
    ({"environment": "hosted_staging"}, "conflicts with classification"),
    ({"classification": "production_accepted"}, "unsupported evidence classification"),
    ({"classification": []}, "unsupported evidence classification"),
    ({"run_id": True}, "positive integers"),
    ({"run_id": "1001"}, "positive integers"),
    ({"attempt": 0}, "positive integers"),
    ({"attempt": False}, "positive integers"),
    ({"attempt": 1.0}, "positive integers"),
    ({"observed_on": "20261106"}, "observation date"),
    ({"observed_on": "2026-02-30"}, "observation date"),
    ({"producer": ""}, "producer identifier"),
])
def test_invalid_run_claims_are_rejected(changes, problem):
    with pytest.raises(intake.IntakeError, match=problem):
        validate(run(**changes))


@pytest.mark.parametrize("record", [
    pr(classification="main_push", source_sha=RELEASE, workflow_head_sha=RELEASE, head_branch="main"),
    wrapper(classification="main_push", head_branch="main"),
    wrapper(workflow_head_sha=RELEASE),
])
def test_relabelling_pr_or_wrapper_cannot_qualify_main(record):
    with pytest.raises(intake.IntakeError):
        validate(record)


def test_main_requires_explicit_release_sha_and_pr_can_be_checked_without_it():
    with pytest.raises(intake.IntakeError, match="explicit release SHA"):
        validate(run(), release_sha=None)
    assert validate(pr(), release_sha=None)[0]["classification"] == "pr_head"
    with pytest.raises(intake.IntakeError, match="complete Git SHA"):
        validate(pr(), release_sha=RELEASE[:8])


@pytest.mark.parametrize(("status", "conclusion"), [
    ("queued", "success"), ("in_progress", "failure"), ("completed", None),
    ("completed", "accepted"), ("unknown", None),
])
def test_status_and_conclusion_are_explicit_and_consistent(status, conclusion):
    with pytest.raises(intake.IntakeError, match="conclusion"):
        validate(run(status=status, conclusion=conclusion))


def test_pending_and_cancelled_observations_preserve_observed_results():
    queued = run(status="queued", conclusion=None, stages=[stage("image-build", "NOT RUN")])
    cancelled = run(run_id=1002, conclusion="cancelled", stages=[stage("image-build", "PASS")])
    rows = validate(queued, cancelled)
    assert [r["conclusion"] for r in rows] == [None, "cancelled"]
    assert [r["stages"][0]["outcome"] for r in rows] == ["NOT RUN", "PASS"]


@pytest.mark.parametrize("status", ["queued", "completed"])
def test_contradictory_stage_results_are_rejected(status):
    conclusion = "success" if status == "completed" else None
    with pytest.raises(intake.IntakeError, match="conflicts"):
        validate(run(status=status, conclusion=conclusion, stages=[stage("image-build", "FAIL")]))


def test_failed_initial_attempts_and_successful_retries_are_preserved():
    npm_failure = pr(conclusion="failure", stages=[
        stage("build", "FAIL", failure_category="npm_etarget"),
        stage("campaign", "NOT RUN", kind="scenario"),
    ])
    csp_failure = pr(run_id=1003, conclusion="failure", stages=[
        stage("build", "PASS"),
        stage("csp", "FAIL", failure_category="http_422_request_schema_envelope"),
        stage("campaign", "SKIP"),
        stage("campaign", "NOT RUN", kind="scenario"),
    ])
    npm_retry = pr(attempt=2, stages=[stage("build", "PASS")])
    csp_retry = pr(run_id=1003, attempt=2, stages=[stage("csp", "PASS")])
    rows = validate(csp_retry, npm_retry, csp_failure, npm_failure)
    assert rows == validate(npm_failure, csp_failure, npm_retry, csp_retry)
    assert [(r["run_id"], r["attempt"], r["conclusion"]) for r in rows] == [
        (1002, 1, "failure"), (1002, 2, "success"), (1003, 1, "failure"), (1003, 2, "success"),
    ]
    assert rows[0]["stages"] == sorted(npm_failure["stages"], key=lambda s: (s["kind"], s["id"]))
    assert rows[2]["stages"] == sorted(csp_failure["stages"], key=lambda s: (s["kind"], s["id"]))
    assert rows[2]["scenario_counts"] == {"PASS": 0, "FAIL": 0, "SKIP": 0, "NOT RUN": 1}


def test_duplicate_attempt_and_inconsistent_run_identity_are_refused():
    with pytest.raises(intake.IntakeError, match="duplicate run attempt"):
        validate(pr(), pr(conclusion="failure"))
    with pytest.raises(intake.IntakeError, match="conflicting identity"):
        validate(pr(), pr(attempt=2, workflow_path=".github/workflows/ci.yml"))
    with pytest.raises(intake.IntakeError, match="conflicting identity"):
        validate(pr(), pr(attempt=2, source_sha=WRAPPER, workflow_head_sha=WRAPPER))


def test_partial_campaign_retains_external_not_run_beside_success():
    stages = [
        stage("hydration", "PASS", kind="scenario"),
        stage("synthetic-account", "PASS", kind="scenario"),
        stage("hosted-staging", "NOT RUN", kind="scenario"),
        stage("live-provider", "NOT RUN", kind="scenario"),
        stage("conditional-step", "SKIP"),
    ]
    row, = validate(run(stages=stages))
    assert row["conclusion"] == "success"
    assert row["scenario_counts"] == {"PASS": 2, "FAIL": 0, "SKIP": 0, "NOT RUN": 2}


@pytest.mark.parametrize("stage_value", [
    stage("test", "UNKNOWN"), stage("test", "PASS", failure_category="error"),
    stage("test", "PASS", kind="gate"), {**stage("test", "PASS"), "gate_acceptance": "PASS"},
])
def test_unknown_stage_outcomes_and_gate_claims_are_refused(stage_value):
    with pytest.raises(intake.IntakeError):
        validate(run(stages=[stage_value]))


def test_duplicate_stage_identity_is_refused():
    with pytest.raises(intake.IntakeError, match="duplicate stage identity"):
        validate(run(stages=[stage("csp", "PASS"), stage("csp", "SKIP")]))


@pytest.mark.parametrize("approval", ["hosted_staging", "legal", "human_qualification", "language_gate", "gate_acceptance"])
def test_successful_synthetic_result_cannot_write_an_approval(approval):
    with pytest.raises(intake.IntakeError, match="unexpected fields"):
        validate(run(**{approval: "PASS"}))
    with pytest.raises(intake.IntakeError, match="unexpected fields"):
        intake.validate_intake({**document(run()), approval: "PASS"}, release_sha=RELEASE)


def test_metadata_availability_and_hash_verification_are_distinct(tmp_path):
    main = run()
    main["artifacts"].append(artifact(main))
    assert validate(main)[0]["artifacts"][0]["archive_verification"] == "not_checked"
    assert validate(main, archives=tmp_path)[0]["artifacts"][0]["archive_verification"] == "not_available"
    local = tmp_path / "2001.zip"
    local.write_bytes(b"synthetic archive bytes")
    assert validate(main, archives=tmp_path)[0]["artifacts"][0]["archive_verification"] == "verified"
    local.write_bytes(b"unrelated image or manifest content")
    with pytest.raises(intake.IntakeError, match="SHA-256 mismatch"):
        validate(main, archives=tmp_path)


def test_archive_symlink_is_refused(tmp_path):
    main = run()
    main["artifacts"].append(artifact(main))
    target = tmp_path / "other.zip"
    target.write_bytes(b"synthetic archive bytes")
    (tmp_path / "2001.zip").symlink_to(target)
    with pytest.raises(intake.IntakeError, match="regular local file"):
        validate(main, archives=tmp_path)


@pytest.mark.parametrize(("override", "problem"), [
    ({"run_id": 2001}, "belongs to a different"),
    ({"attempt": 2}, "belongs to a different"),
    ({"attempt": True}, "belongs to a different"),
    ({"workflow_repository": intake.PRIVATE_WRAPPER_REPO}, "belongs to a different"),
    ({"id": True}, "invalid artifact ID"),
    ({"sha256": RELEASE}, "64 lowercase hex digits"),
    ({"sha256": "g" * 64}, "64 lowercase hex digits"),
    ({"sha256": None}, "64 lowercase hex digits"),
    ({"sha256": "sha256:" + "0" * 64}, "64 lowercase hex digits"),
    ({"manifest_sha256": "f" * 64}, "unexpected fields"),
])
def test_artifact_attribution_and_digest_schema(override, problem):
    main = run()
    main["artifacts"].append(artifact(main, **override))
    with pytest.raises(intake.IntakeError, match=problem):
        validate(main)


def test_duplicate_artifact_id_rejected_across_attempts_and_runs():
    first = pr()
    first["artifacts"].append(artifact(first))
    for second in (pr(attempt=2), pr(run_id=1003)):
        second["artifacts"].append(artifact(second))
        with pytest.raises(intake.IntakeError, match="conflicting attribution"):
            validate(first, second)


def test_missing_required_fields_and_empty_document_fail_closed():
    main = run()
    del main["source_sha"]
    with pytest.raises(intake.IntakeError, match="missing or unexpected fields"):
        validate(main)
    with pytest.raises(intake.IntakeError, match="nonempty"):
        validate()


def test_cli_validates_read_only_and_rejects_duplicate_json_keys(tmp_path, capsys):
    source = tmp_path / "reviewed.json"
    data = json.dumps(document(run()))
    source.write_text(data, encoding="utf-8")
    args = [str(source), "--release-sha", RELEASE]
    assert intake.main(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["observations"][0]["run_id"] == 1001
    assert source.read_text(encoding="utf-8") == data
    source.write_text(data.replace('"attempt": 1', '"attempt": 1, "attempt": 2'), encoding="utf-8")
    assert intake.main(args) == 1
    assert "duplicate object key" in capsys.readouterr().out


@pytest.mark.parametrize("data", ["{", "[" * 3000, "9" * 5000 + "x"])
def test_cli_returns_controlled_failure_for_invalid_json(data, tmp_path, capsys):
    source = tmp_path / "reviewed.json"
    source.write_text(data, encoding="utf-8")
    assert intake.main([str(source)]) == 1
    assert capsys.readouterr().out == "FAIL: could not read a valid local JSON input\n"
