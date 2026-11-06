# 08A0 offline exact-run evidence intake

`scripts/production/exact_run_evidence.py` validates a reviewed JSON packet and prints a deterministic observation report. The intake records CI and disposable execution evidence alongside the existing 08A0 pipeline. The acceptance ledger, tracker, generated views and their five layers remain authoritative for their respective statuses.

```sh
python scripts/production/exact_run_evidence.py /path/to/reviewed.json --release-sha FULL_COMMIT_SHA
python scripts/production/exact_run_evidence.py /path/to/reviewed.json --release-sha FULL_COMMIT_SHA --archives /path/to/approved-archives
```

Pass the independently verified release SHA whenever the packet includes a `main_push` observation. If it includes a `private_wrapper` observation, pass the separately reviewed runner repository with `--wrapper-repository`. Inputs and optional archive bytes stay local. The CLI uses the standard library and writes its report only to stdout. Validation errors exit nonzero.

## Version 1 input

The envelope has `schema: "ask4mo.exact_run_evidence.v1"` and a nonempty `records` array. Each record supplies all the fields in this synthetic example.

```json
{
  "schema": "ask4mo.exact_run_evidence.v1",
  "records": [
    {
      "source_repository": "moaltamimi-unbiasedtalent/Intelligent-Interview-Coach",
      "source_sha": "1111111111111111111111111111111111111111",
      "workflow_repository": "moaltamimi-unbiasedtalent/Intelligent-Interview-Coach",
      "workflow_path": ".github/workflows/immutable-release.yml",
      "workflow_head_sha": "1111111111111111111111111111111111111111",
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
      "stages": [
        {
          "kind": "step",
          "id": "csp-qualification",
          "outcome": "PASS",
          "failure_category": null
        },
        {
          "kind": "scenario",
          "id": "live-email-and-oidc",
          "outcome": "NOT RUN",
          "failure_category": null
        }
      ],
      "artifacts": [
        {
          "workflow_repository": "moaltamimi-unbiasedtalent/Intelligent-Interview-Coach",
          "run_id": 1001,
          "attempt": 1,
          "id": 2001,
          "name": "csp-hydration-evidence",
          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        }
      ]
    }
  ]
}
```

| Classification | Required provenance |
|---|---|
| `main_push` | Canonical repo, GitHub-hosted `push` on `main`, one of the seven reviewed workflows, full execution source and workflow head both equal to the explicit release SHA. |
| `pr_head` | Canonical repo, GitHub-hosted `pull_request`, reviewed checkout SHA equals the full workflow head SHA. |
| `manual_dispatch` | Canonical repo, GitHub-hosted `workflow_dispatch`, reviewed checkout SHA equals the full workflow head SHA. |
| `private_wrapper` | Independently supplied `--wrapper-repository owner/repository`, `push`, disposable Linux/amd64, distinct full workflow-head and Ask4Mo execution-source SHAs. |

- Capture `source_sha` from the checked-out source evidence. For a PR job using a default merge-ref checkout, the run head alone cannot establish a `pr_head` observation. Supply only proven bindings. The `main_push` workflow list defines which individual observations this version can accept. The report makes no workflow-quorum decision.
- Record the run lifecycle separately from measured stages. A completed run has a terminal conclusion. An unfinished run has an explicit `null` conclusion. Stages use `job`, `step` or `scenario` and preserve `PASS`, `FAIL`, `SKIP` and `NOT RUN`. An empty stage list records run-level evidence only. Capture failure categories as bounded identifiers, or `null` where the category is unavailable. For successful workflow observations, submitted stages describe effective qualification outcomes. Keep raw tolerated errors in their original diagnostics.
- Use one reviewed observation per workflow repository, run ID and attempt in a packet. A retry gets its own record. The validator rejects duplicate attempts and changed workflow or source identities across attempts. Keep previous observations in the retained source evidence. The validator preserves every attempt supplied to it and cannot find omitted attempts offline.
- List artifacts only when the producer has verified attribution to the same workflow repository, run and attempt. A run-level artifact list can span retries. Verify upload provenance before recording an attempt. Supply `sha256` for the artifact archive, with 64 lowercase hex digits and no prefix. Git commit IDs, image IDs and manifest digests have separate meanings.
- With `--archives`, only explicitly named `<artifact ID>.zip` entries in the operator-selected directory are read. Archive names from JSON are never used as paths. Matching bytes yield `verified`, missing bytes `not_available`, and a mismatched digest fails validation. Without the option, verification is `not_checked`. The checker hashes bytes without extracting archives. Select a trusted local directory containing only evidence archives.

Use reviewed, sanitized metadata. Offline validation checks consistency and optional archive integrity. The observer still establishes GitHub run identity, checkout, attempt attribution and artifact provenance from retained evidence. This report has no acceptance fields or write path. A successful synthetic campaign can retain external `NOT RUN` scenarios and provides no hosted, legal, independent human, language or gate approval.

## Tests

```sh
python -m pytest tests/test_exact_run_evidence.py tests/test_release_evidence_08a0.py
python scripts/production/release_evidence.py check
```

The tests use synthetic data. The reviewed 6 November packet can be checked by projecting its independently verified run, attempt and artifact metadata into a local input file. The full packet, original npm-prune and CSP failure artifacts, and later successful attempts retain their original evidence identities.
