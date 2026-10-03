#!/usr/bin/env python
"""P10B-W10.9 jobs guard (deterministic, offline, 0 paid/live calls).

High-risk invariants of the durable job system: DB-backed queue with no external broker, a separate worker entrypoint,
a code-defined job registry (no arbitrary handler names, no shell jobs), PostgreSQL SKIP LOCKED and SQLite atomic
claim paths, leases/heartbeat/retry/idempotency, no raw payload exposure to Admin, permissioned Admin routes, no
platform pause (SEC-W10-05 stays open) and the migration chain. It does not duplicate the test suite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BROKERS = ("celery", "kombu", "rabbitmq", "pika", "kafka", "apscheduler", "dramatiq", "huey")


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    svc, reg, wrk = read("src/jobs/service.py"), read("src/jobs/registry.py"), read("src/jobs/worker.py")
    route = read("src/api/routes/admin_jobs.py")
    deps = " ".join(read(f) for f in ("pyproject.toml", "requirements.txt", "requirements-dev.txt")).lower()
    check("no_external_broker_dependency", not any(b in deps for b in BROKERS), "none declared")
    check("no_broker_in_job_code", not any(b in (svc + reg + wrk).lower() for b in BROKERS), "none imported")
    check("db_backed_jobs_table", "class Job(Base)" in read("src/persistence.py") and 'Job' in svc, "jobs table")
    check("separate_worker_entrypoint", "def main()" in wrk and '__name__ == "__main__"' in wrk, "python -m src.jobs.worker")
    main_py, routes_dir = read("src/api/main.py"), " ".join(p.read_text() for p in (ROOT / "src/api/routes").glob("*.py"))
    check("api_never_runs_worker", "src.jobs.worker" not in main_py + routes_dir and "Worker(" not in routes_dir, "worker not imported by the API")
    check("postgres_skip_locked_claim", "with_for_update(skip_locked=True)" in svc and 'dialect.name == "postgresql"' in svc, "present")
    check("sqlite_atomic_conditional_claim", "Job.attempts == seen" in svc and "res.rowcount != 1" in svc, "guarded UPDATE + rowcount")
    check("claim_does_not_hold_handler_transaction", svc.count("s.commit()") >= 6 and "handler(" not in svc, "handler runs in the worker, outside claim")
    check("lease_expiry_and_reaper", "def reap_expired" in svc and "lease_expired" in svc, "present")
    check("heartbeat_owner_guarded", "def heartbeat" in svc and "Job.lease_expires_at > now" in svc and "_owned(claim)" in svc, "present")
    check("lifecycle_writes_guarded_by_lease_owner", svc.count("_owned(claim)") >= 3 and "LeaseLost" in svc, "complete/fail/heartbeat")
    check("retry_policy_and_backoff_code_defined", "def backoff_seconds" in reg and "backoff_cap_seconds" in reg and "max_attempts" in reg, "present")
    check("no_sleep_in_worker_execution", "time.sleep" not in wrk and "sleep(" not in svc, "backoff sets available_at")
    check("enqueue_idempotency_constraint", "uq_jobs_active_idempotency" in read("src/persistence.py") and "uq_jobs_active_idempotency" in read("migrations/versions/0018_jobs.py"), "partial unique index")
    check("single_enqueue_service", "def enqueue" in svc and "Job(" not in route and "Job(" not in wrk, "only JobService creates rows")
    check("registry_is_code_defined", "REGISTRY" in reg and "build_registry" in reg, "present")
    check("no_shell_or_dynamic_handler", not re.search(r"subprocess|os\.system|importlib|eval\(|exec\(|__import__", svc + reg + wrk + route), "none")
    check("payload_validated_and_secret_keys_rejected", "reject_secret_like_keys" in reg and "extra=\"forbid\"" in reg, "present")
    check("failure_messages_are_fixed_not_exception_text", "SAFE_MESSAGES" in reg and "str(exc)" not in svc + wrk, "fixed wording")
    schema = read("src/api/schemas/admin.py")
    block = schema[schema.index("class JobLease"):schema.index("class JobEnqueueRequest")] if "class JobLease" in schema else ""
    check("no_raw_payload_in_admin_schemas", block != "" and "payload_json" not in block and "payload:" not in block.replace("payload_summary", ""), "response models carry summary only")
    check("no_raw_payload_in_view", '"payload_json"' not in svc[svc.index("def _view"):svc.index("def get(")] and '"payload"' not in svc[svc.index("def _view"):svc.index("def get(")], "view uses typed summary")
    check("admin_routes_permissioned", route.count("require_permission(") >= 7 and "JOBS_READ" in route and "JOBS_MANAGE" in route, "7 routes")
    check("no_state_edit_route", not re.search(r'router\.(put|patch|delete)', route), "GET/POST only")
    check("no_payload_search", "Job.public_id == q" in svc and "payload_json" not in svc[svc.index("def list("):svc.index("def stats(")], "public id only")
    check("uses_existing_permissions", '"platform.jobs.read"' in read("src/application/admin_permissions.py") and '"platform.jobs.manage"' in read("src/application/admin_permissions.py"), "no new permission")
    check("no_platform_pause_added", "pause" not in (svc + reg + wrk + route).lower(), "SEC-W10-05 remains open")
    mig = read("migrations/versions/0018_jobs.py")
    check("migration_chain_valid", 'down_revision = "0017_integrations"' in mig and "ck_jobs_lease_matches_state" in mig and "ck_jobs_state" in mig, "0018 chains from 0017")
    tests = read("tests/test_jobs_w10_9.py")
    check("tests_exist", all(t in tests for t in (
        "test_concurrent_workers_claim_each_job_exactly_once", "test_crash_recovery_reclaims_after_lease_expiry_and_completes",
        "test_heartbeat_rules", "test_retry_backoff_max_attempts_and_terminal_failure",
        "test_handler_replay_after_crash_window_has_one_domain_effect", "test_postgres_two_workers_one_claim",
        "test_worker_lease_lost_discards_result_and_does_not_overwrite")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.9 JOBS GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:62s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
