"""Validate reviewed 08A0 run observations offline, independently of acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = "ask4mo.exact_run_evidence.v1"
REPO = "moaltamimi-unbiasedtalent/Intelligent-Interview-Coach"
# The classification describes provenance, not the purpose or acceptance of a test.
CLASSIFICATIONS = {
    "main_push": ("push", "github_hosted_ci"),
    "pr_head": ("pull_request", "github_hosted_ci"),
    "manual_dispatch": ("workflow_dispatch", "github_hosted_ci"),
    "private_wrapper": ("push", "disposable_linux_amd64"),
}
# The reviewed push checks supported by this intake version.
MAIN_WORKFLOWS = frozenset(
    f".github/workflows/{name}.yml"
    for name in ("ci", "immutable-release", "redis-limiter", "staging-migration",
                 "recovery", "agent-admission", "ai-budget")
)
UNFINISHED = {"queued", "in_progress", "pending", "requested", "waiting"}
CONCLUSIONS = {
    "success", "failure", "cancelled", "skipped", "timed_out", "action_required",
    "neutral", "stale", "startup_failure",
}
OUTCOMES = ("PASS", "FAIL", "SKIP", "NOT RUN")
RECORD_FIELDS = frozenset("""
    source_repository source_sha workflow_repository workflow_path workflow_head_sha
    head_branch event run_id attempt environment classification status conclusion
    producer observed_on stages artifacts
""".split())
STAGE_FIELDS = frozenset({"kind", "id", "outcome", "failure_category"})
ARTIFACT_FIELDS = frozenset({"workflow_repository", "run_id", "attempt", "id", "name", "sha256"})
SHA = r"[0-9a-f]{40}"
TOKEN = r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}"


class IntakeError(ValueError):
    """A safe validation error that does not echo input values."""


def require(condition: bool, where: str, problem: str) -> None:
    if not condition:
        raise IntakeError(f"{where}: {problem}")


def shape(value: Any, fields: frozenset[str], where: str) -> None:
    require(isinstance(value, dict) and value.keys() == fields, where, "missing or unexpected fields")


def matches(value: Any, pattern: str) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def is_sha(value: Any) -> bool:
    return matches(value, SHA) and value != "0" * 40


def positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def valid_date(value: Any) -> bool:
    if not matches(value, r"[0-9]{4}-[0-9]{2}-[0-9]{2}"):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_run(record: dict, where: str, release_sha: str | None, wrapper_repository: str | None) -> None:
    classification = record["classification"]
    require(isinstance(classification, str) and classification in CLASSIFICATIONS,
            where, "unsupported evidence classification")
    workflow_repository = wrapper_repository if classification == "private_wrapper" else REPO
    require(workflow_repository is not None, where, "private wrapper requires an explicit workflow repository")
    expected = (workflow_repository, *CLASSIFICATIONS[classification])
    actual = (record["workflow_repository"], record["event"], record["environment"])
    require(actual == expected, where, "workflow repository, event or environment conflicts with classification")
    require(record["source_repository"] == REPO, where, "unexpected source repository")
    require(matches(record["workflow_path"], r"\.github/workflows/[a-zA-Z0-9][a-zA-Z0-9_.-]*\.ya?ml"),
            where, "invalid workflow path")
    require(matches(record["head_branch"], r"[a-zA-Z0-9_][a-zA-Z0-9_./-]{0,254}"),
            where, "invalid head branch")
    source, head = record["source_sha"], record["workflow_head_sha"]
    require(is_sha(source) and is_sha(head), where, "source and workflow head must be complete Git SHAs")
    if classification == "private_wrapper":
        require(source != head, where, "private wrapper must bind a distinct checked source")
    else:
        require(source == head, where, "checked source does not match workflow head")
    if classification == "main_push":
        require(record["workflow_path"] in MAIN_WORKFLOWS, where, "unsupported main push workflow")
        require(record["head_branch"] == "main" and source == release_sha,
                where, "main push must match main branch and explicit release SHA")
    require(positive_int(record["run_id"]) and positive_int(record["attempt"]),
            where, "run ID and attempt must be positive integers")
    require(matches(record["producer"], TOKEN) and valid_date(record["observed_on"]),
            where, "producer identifier and ISO observation date are required")
    status, conclusion = record["status"], record["conclusion"]
    if status == "completed":
        require(isinstance(conclusion, str) and conclusion in CONCLUSIONS, where, "invalid completed conclusion")
    else:
        require(isinstance(status, str) and status in UNFINISHED and conclusion is None,
                where, "unfinished status requires an explicit null conclusion")


def validate_stages(record: dict, where: str) -> None:
    stages = record["stages"]
    require(isinstance(stages, list), where, "stages must be an array")
    seen = set()
    for number, stage in enumerate(stages):
        path = f"{where}.stages[{number}]"
        shape(stage, STAGE_FIELDS, path)
        kind, identifier, outcome = stage["kind"], stage["id"], stage["outcome"]
        require(kind in ("job", "step", "scenario") and matches(identifier, TOKEN), path, "invalid stage identity")
        require((kind, identifier) not in seen, path, "duplicate stage identity")
        seen.add((kind, identifier))
        require(outcome in OUTCOMES, path, "invalid stage outcome")
        category = stage["failure_category"]
        require(category is None or (outcome == "FAIL" and matches(category, TOKEN)),
                path, "failure category requires a failed stage")
        if record["conclusion"] == "success":
            require(outcome != "FAIL", path, "failed stage conflicts with success")
        if record["conclusion"] == "skipped" or record["status"] in {"queued", "pending", "requested"}:
            allowed = ("SKIP", "NOT RUN") if record["conclusion"] == "skipped" else ("NOT RUN",)
            require(outcome in allowed, path, "stage outcome conflicts with workflow status")


def validate_artifacts(record: dict, where: str, artifact_ids: set[int]) -> None:
    artifacts = record["artifacts"]
    require(isinstance(artifacts, list), where, "artifacts must be an array")
    for number, artifact in enumerate(artifacts):
        path = f"{where}.artifacts[{number}]"
        shape(artifact, ARTIFACT_FIELDS, path)
        identifier = artifact["id"]
        require(positive_int(identifier) and matches(artifact["name"], r"[a-zA-Z0-9][a-zA-Z0-9 ._-]{0,127}"),
                path, "invalid artifact ID or name")
        require(matches(artifact["sha256"], r"[0-9a-f]{64}"), path, "artifact SHA-256 must be 64 lowercase hex digits")
        require(positive_int(artifact["run_id"]) and positive_int(artifact["attempt"])
                and all(artifact[key] == record[key] for key in ("workflow_repository", "run_id", "attempt")),
                path, "artifact belongs to a different repository, run or attempt")
        require(identifier not in artifact_ids, path, "duplicate artifact ID or conflicting attribution")
        artifact_ids.add(identifier)


def verify_archive(artifact: dict, archives: Path | None) -> str:
    if archives is None:
        return "not_checked"
    path = archives / f"{artifact['id']}.zip"
    try:
        # A directory entry cannot turn a hash check into an indirect read or FIFO wait.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return "not_available"
    except OSError:
        raise IntakeError("artifact archive: cannot open a regular local file") from None
    try:
        with os.fdopen(fd, "rb") as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode),
                    "artifact archive", "expected a regular local file")
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise IntakeError("artifact archive: could not read local bytes") from None
    require(digest.hexdigest() == artifact["sha256"], "artifact archive", "SHA-256 mismatch")
    return "verified"


def validate_intake(
    document: Any, *, release_sha: str | None = None, wrapper_repository: str | None = None,
    archives: Path | None = None,
) -> dict:
    """Return a stable observation report. The reviewed inputs supply provenance."""
    shape(document, frozenset({"schema", "records"}), "intake")
    require(document["schema"] == SCHEMA, "intake", "unsupported schema")
    require(release_sha is None or is_sha(release_sha), "release SHA", "expected a complete Git SHA")
    require(wrapper_repository is None or (
        matches(wrapper_repository, r"[a-zA-Z0-9][a-zA-Z0-9-]*/[a-zA-Z0-9_][a-zA-Z0-9_.-]*")
        and wrapper_repository.casefold() != REPO.casefold()
    ), "wrapper repository", "expected a separate owner/repository identifier")
    records = document["records"]
    require(isinstance(records, list) and bool(records), "intake", "records must be a nonempty array")
    seen = set()
    run_sources = {}
    artifact_ids: set[int] = set()
    for number, record in enumerate(records):
        where = f"records[{number}]"
        shape(record, RECORD_FIELDS, where)
        validate_run(record, where, release_sha, wrapper_repository)
        run = (record["workflow_repository"], record["run_id"])
        attempt = (*run, record["attempt"])
        require(attempt not in seen, where, "duplicate run attempt")
        seen.add(attempt)
        identity = tuple(record[key] for key in (
            "workflow_path", "workflow_head_sha", "head_branch", "source_sha", "classification",
        ))
        require(run_sources.setdefault(run, identity) == identity, where, "conflicting identity across run attempts")
        validate_stages(record, where)
        validate_artifacts(record, where, artifact_ids)

    require(archives is None or archives.is_dir(), "archives", "expected a local directory")
    observations = []
    for record in sorted(records, key=lambda r: (r["workflow_repository"], r["run_id"], r["attempt"])):
        stages = sorted(record["stages"], key=lambda s: (s["kind"], s["id"]))
        counts = Counter(s["outcome"] for s in stages if s["kind"] == "scenario")
        artifacts = [
            {**a, "archive_verification": verify_archive(a, archives)}
            for a in sorted(record["artifacts"], key=lambda a: a["id"])
        ]
        observations.append({
            **record,
            "stages": stages,
            "artifacts": artifacts,
            "scenario_counts": {outcome: counts[outcome] for outcome in OUTCOMES},
        })
    return {"schema": "ask4mo.exact_run_observations.v1", "observations": observations}


def unique_json_keys(pairs: list[tuple[str, Any]]) -> dict:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "input JSON", "duplicate object key")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="reviewed local JSON observations")
    parser.add_argument("--release-sha", help="full release commit, required for main_push observations")
    parser.add_argument("--wrapper-repository", help="independently reviewed owner/repository for private wrapper records")
    parser.add_argument("--archives", type=Path, help="local directory of optional <artifact ID>.zip files")
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_json_keys)
        report = validate_intake(document, release_sha=args.release_sha, wrapper_repository=args.wrapper_repository,
                                 archives=args.archives)
    except IntakeError as exc:
        print(f"FAIL: {exc}")
        return 1
    except (OSError, ValueError, RecursionError):
        print("FAIL: could not read a valid local JSON input")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
