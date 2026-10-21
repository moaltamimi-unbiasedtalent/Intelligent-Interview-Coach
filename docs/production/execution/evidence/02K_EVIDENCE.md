# 02K Evidence: Knowledge runtime, index manifest and persistence contracts

Branch `feat/02k-knowledge-contract`, base `origin/main` 38eabbc. Interface package: a typed contract plus a conformance suite, no behaviour change.

## Requirement IDs
REQ-OWN-05 K3 and K4; REVIEW-04 R1, R4, R5 (contract part only).

## Contract summary (`src/knowledge_admin/contracts.py`, `SCHEMA_VERSION = 1`)
- `RuntimeIdentity`: database kind plus SHA-256 fingerprint of `kind://host:port/name` (credentials, query string and driver suffix excluded), data root label plus 12-hex hash of the path, collections with chunk counts (None if unreadable), embedding provider/model/dimensions/degradation, worker heartbeat summary. `build_runtime_identity(config, session_factory=None, *, stores, job_stats, data_root)` reads only objects it is given. `identities_compatible(api, worker)` returns a `CompatibilityReport` (list of `Mismatch`); unknown is never a match; chunk counts and heartbeats are not compared.
- `IndexManifestV2` (provider, model, version, dimensions, metric, collection id, checksum, per-source checksums, built_at, source version ids, `compatibility_hash`, `degraded`, `degradation_reason`). The hash is computed from (provider, model, version, dimensions) and recomputed on load, so it cannot be forged; it is None if any input is unknown. `embedder_matches(manifest, EmbedderIdentity)` returns `EmbedderMatch` (mismatched and unknown fields). `parse_build_metadata` and `parse_index_record` read the existing formats read-only and leave missing fields None.
- Scanner: `ScanVerdict` (clean, infected, unavailable), `ScanOutcome`, `ScannerProtocol`, `LegacyScannerAdapter` over `FileSecurityScanner`, `scan_accepted(outcome, required=)` (fail-closed; the suite asserts it agrees with `enforce_scan` for every scanner and required combination). `file_security.py` is untouched.

Invariants are listed in the module docstring.

## Security and privacy impact
No secret, URL, credential, absolute path or vector appears in any serialised identity, manifest or report (asserted on the JSON strings, including a hostile password in the URL and query string, and an exception message from a broken store). No network, provider, database write or file write. No migration. No existing endpoint or retrieval path imports the module.

## Files
- `src/knowledge_admin/contracts.py` (new)
- `tests/contracts/__init__.py`, `tests/contracts/test_knowledge_contract_02k.py` (new)
- this file

## Tests and commands
| Check | Result |
|---|---|
| `py_compile` of both new modules | pass |
| `scripts/ci_test_shards.py verify --shards 4` | OK, 266 test files each in exactly one shard |
| First run of `tests/contracts` (/tmp/ci_venv) | 3 failed (see rework) |
| After fix, repo `.venv`: `tests/contracts` + `test_knowledge_admin_w10_8` + `test_knowledge_readiness_w12_4a` + `test_p8_hardening` + `test_security_hardening` + `test_company_upload_limits` | 125 passed |
| Same set under `/tmp/ci_venv` | 125 passed |
| `ruff check .` (both venvs) | All checks passed |

Rework round 1 (found by the first execution): (a) the worker summary reported `none` instead of `unknown` when no job stats were supplied; fixed. (b) `scan_accepted(required=False)` accepted an UNAVAILABLE outcome, but `enforce_scan` calls the scanner even when optional and a scanner that cannot scan raises, so it fails closed; the rule is now "only a CLEAN verdict can pass" (plus a real scan when required), and the test double that wrongly asserted was fixed. No public names or signatures changed; the two behaviours above are documented in the docstrings.

## Regression evidence
No existing file was modified (additions only), so existing tests cannot be affected except through discovery, which the shard verification covers.

## Remaining risks
- `database_fingerprint` hashes a low-entropy string; it is non-reversible in practice for URLs but a host/name guess can be confirmed. Never expose it publicly.
- The index record never stored provider/model/dimensions, so records built before 02B stay "unknown" and incompatible until re-indexed; this is intended.
- Embedding "version" has no existing source, so live embedders report unknown until 02B defines it.
- The degradation rule (auto/openai configured but local resolved) is a contract decision 02B may refine.

## Throughput record
- Start: 2026-10-21 18:03 UTC. End: about 18:40 UTC, including an interpreter outage that blocked test runs for roughly 15 minutes.
- Estimate 2-3 engineering days; actual wall-clock about 0.6 hours.
- Rework rounds (fix commits after first push): 1 (this commit).
- CI duration: pending (CI runs only once a PR exists).
- SHA and CI result: see the final report.
