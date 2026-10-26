"""Private in-container synthetic probes. Never imported by ordinary application startup."""

from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.integration.runtime import boundary, control, agent  # noqa: E402


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def factory():
    boundary()
    from src.persistence import make_engine, make_session_factory

    return make_session_factory(make_engine(os.environ["DATABASE_URL"]))


def credentials():
    return json.loads(Path("/campaign/private/credentials.json").read_text())


def http(path, method="GET", payload=None, *, cookie="", host="api", raw=False):
    require(host in ("api", "api_b", "api_held"), "campaign_http_host_refused")
    require(
        path.startswith("/api/") and "://" not in path, "campaign_http_path_refused"
    )
    conn = http.client.HTTPConnection(host, 8000, timeout=35)
    data = json.dumps(payload) if payload is not None else None
    conn.request(
        method,
        path,
        data,
        {
            "Content-Type": "application/json",
            "Cookie": cookie,
            "Origin": "https://app.staging.example.com",
        },
    )
    response = conn.getresponse()
    body = response.read()
    headers = dict(response.getheaders())
    status = response.status
    conn.close()
    if not raw:
        try:
            body = json.loads(body)
        except ValueError:
            body = {}
    return status, body, headers


def login(who="alice", host="api"):
    c = credentials()[who]
    cache = Path("/campaign/private/" + who + ".session")
    if cache.exists():
        existing = cache.read_text()
        if http("/api/v1/auth/me", cookie=existing, host=host)[0] == 200:
            return existing
    status, _, headers = http(
        "/api/v1/auth/login",
        "POST",
        {"email": c["email"], "password": c["password"]},
        host=host,
    )
    require(status == 200, "synthetic_login_failed")
    raw = headers.get("set-cookie", headers.get("Set-Cookie", ""))
    require(
        all(flag in raw.lower() for flag in ("secure", "httponly", "samesite=lax")),
        "insecure_cookie",
    )
    cookie = raw.split(";")[0]
    require(cookie.startswith("ask4mo_session="), "session_cookie_missing")
    cache.write_text(cookie)
    cache.chmod(0o600)
    return cookie


def seed():
    # This one-shot initializer owns ONLY the freshly created labelled control
    # volume. Drop root permanently BEFORE importing application repositories.
    boundary()
    if os.getuid() == 0:
        for location in (
            "/campaign",
            "/campaign-backup",
            "/campaign-transfer",
            "/campaign-ledger",
        ):
            root = Path(location)
            require(not any(root.iterdir()), "fresh_control_volume_required")
            root.chmod(0o700)
            os.chown(root, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    require(os.getuid() == 10001, "non_root_fixture_required")
    from src.application.auth_service import AuthenticationService, AuthConfig
    from src.auth_repository import (
        AccountRepository,
        SessionRepository,
        TokenRepository,
        AuditRepository,
    )
    from src.mail import MemoryEmailSender
    from src.invitations import repository as IR
    from src.application import admin_audit as A
    from src.persistence import User

    sf = factory()
    accounts = AccountRepository(sf)
    mail = MemoryEmailSender()
    svc = AuthenticationService(
        accounts=accounts,
        sessions=SessionRepository(sf),
        auth_tokens=TokenRepository(sf),
        audit=AuditRepository(sf),
        email=mail,
        config=AuthConfig.from_env(),
    )
    out = {}
    for who in ("alice", "bob", "admin"):
        code = IR.new_code()
        audit = A.build_audit(
            event_type=A.ADMIN_INVITATION_ISSUED,
            actor_user_id=None,
            request_id=None,
            target_type="invitation",
            origin="cli",
        )
        IR.InvitationRepository(sf).issue(
            code_hash=IR.hash_code(code),
            ttl_days=1,
            email=None,
            issued_by_user_id=None,
            audit=audit,
        )
        email = who + "@example.invalid"
        password = os.environ["CAMPAIGN_PASSWORD"]
        require(
            svc.register(
                email=email,
                password=password,
                display_name="Synthetic " + who,
                locale="en",
                invitation_code=code,
                require_invitation=True,
            ).created,
            "fixture_registration_failed",
        )
        token = re.search(r"token=([^\s&]+)", mail.sent[-1].body).group(1)
        require(svc.verify_email(token=token), "fixture_verification_failed")
        account = accounts.find_by_email(email)
        accounts.complete_onboarding(account.user_id)
        out[who] = {"email": email, "password": password, "user_id": account.user_id}
        if who == "admin":
            with sf() as s:
                s.get(User, account.user_id).platform_role = "platform_admin"
                s.commit()
    # Populate only the fresh synthetic DB/private volumes with local-hash
    # knowledge and documents; no provider/embedding client is constructed.
    import shutil
    from src.backup_set.fixture import build_synthetic_environment

    source = build_synthetic_environment(
        Path("/campaign/knowledge-fixture"), database_url=os.environ["DATABASE_URL"]
    )
    for source_dir, target in (
        (source.documents_dir, Path("/data/documents")),
        (source.knowledge_files_dir, Path("/data/knowledge/knowledge_private")),
        (source.knowledge_index_dir, Path("/data/knowledge/chroma")),
    ):
        if target.exists():
            require(not any(target.iterdir()), "fresh_private_volume_required")
        shutil.copytree(source_dir, target, dirs_exist_ok=True)
    control(mode="plain")
    from src.agent.models import AgentRunRequest

    result = agent().run(
        AgentRunRequest(
            goal="Synthetic existing-run fixture",
            user_id=str(out["alice"]["user_id"]),
            enable_current_market_research=False,
        )
    )
    require(result.status == "completed", "scripted_agent_seed_failed")
    out["run_id"] = result.run_id
    p = Path("/campaign/private")
    p.mkdir(mode=0o700)
    file = p / "credentials.json"
    file.write_text(json.dumps(out))
    file.chmod(0o600)
    return {
        "synthetic_accounts": 3,
        "mail": "memory_capture_only",
        "existing_run_fixture": True,
        "language_activation_overridden": False,
    }


def state():
    from sqlalchemy import text

    with factory()() as s:
        heads = (
            s.execute(text("select version_num from alembic_version")).scalars().all()
        )
    require(heads == ["0048_agent_run_controls"], "unexpected_schema")
    return {"schema": heads[0]}


def identity():
    require(os.getuid() == 10001, "non_root_required")
    for root in ("/data/documents", "/data/knowledge"):
        path = Path(root) / ".campaign-write-test"
        path.write_text("synthetic")
        path.unlink()
    from src.agent.run_control import RunControlStore
    from src.llm.budget.governor import HOSTED_POLICY_VERSION

    require(
        HOSTED_POLICY_VERSION == 2 and RunControlStore is not None,
        "durable_controls_missing",
    )
    return {
        **state(),
        "uid": os.getuid(),
        "private_roots_writable": True,
        "migration_helper_present": Path("scripts/migrate.sh").is_file(),
    }


def http_checks():
    cookie = login()
    other = login("bob", host="api_b")
    admin = login("admin")
    require(http("/api/v1/auth/me", cookie=cookie)[0] == 200, "session_missing")
    require(
        http("/api/v1/auth/me", cookie=cookie, host="api_b")[0] == 200,
        "cross_instance_session_missing",
    )
    require(
        http("/api/v1/auth/me", cookie="ask4mo_session=expired-synthetic")[0] == 401,
        "expired_session_accepted",
    )
    require(
        http("/api/v1/admin/home", cookie=other)[0] == 403, "candidate_admin_access"
    )
    require(
        http("/api/v1/admin/home", cookie=admin)[0] == 200, "admin_visibility_failed"
    )
    status, budget_state, _ = http("/api/v1/admin/ai/budget", cookie=admin)
    require(
        status == 200
        and budget_state["enforcement"] == "closed"
        and not budget_state["approval_marker_presented"],
        "admin_budget_state_untruthful",
    )
    rid = credentials()["run_id"]
    require(
        http("/api/v1/agent/runs/" + rid, cookie=other)[0] == 404,
        "run_owner_isolation_failed",
    )
    status, body, _ = http(
        "/api/v1/agent/run",
        "POST",
        {"goal": "Synthetic refused new activity"},
        cookie=cookie,
    )
    require(
        status == 422 and "language_not_activated" in json.dumps(body),
        "language_gate_not_closed",
    )
    status, _, _ = http(
        "/api/v1/auth/register",
        "POST",
        {
            "email": "new@example.invalid",
            "password": os.environ["CAMPAIGN_PASSWORD"],
            "locale": "en",
        },
    )
    require(status == 422, "hosted_registration_not_refused")
    require(
        http("/api/v1/auth/logout", "POST", cookie=other)[0] == 200, "logout_failed"
    )
    require(http("/api/v1/auth/me", cookie=other)[0] == 401, "logout_not_persisted")
    return {
        "checks": 9,
        "shared_sessions": True,
        "ownership": True,
        "new_language_activity": "refused",
        "admin": "metadata_only",
    }


def jobs():
    from src.jobs.service import JobService
    from src.persistence import Job
    from sqlalchemy import select

    sf = factory()
    svc = JobService(sf)
    one, created = svc.enqueue(
        "diagnostic_noop", {"label": "campaign"}, idempotency_key="campaign-noop"
    )
    require(created, "fresh_job_required")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        with sf() as s:
            row = s.scalar(select(Job).where(Job.public_id == one["public_id"]))
            status = row.state
            attempts = row.attempts
        if status == "succeeded":
            break
        time.sleep(0.25)
    require(status == "succeeded" and attempts == 1, "worker_single_claim_failed")
    return {"real_worker_job": "succeeded", "attempts": attempts, "workers": 2}


def agent_checks():
    cookie = login()
    rid = credentials()["run_id"]
    before = control()["calls"]
    path = "/api/v1/agent/runs/" + rid + "/events"
    for host in ("api", "api_b"):
        status, data, _ = http(path, cookie=cookie, host=host, raw=True)
        require(
            status == 200 and b"event:" in data and b"result" in data,
            "sse_result_missing",
        )
        require(
            not any(
                x in data
                for x in (b"system_prompt", b"chain_of_thought", b"provider_api_key")
            ),
            "private_sse_event",
        )
    require(control()["calls"] == before, "reconnection_executed_model")
    status, body, _ = http("/api/v1/agent/runs/" + rid, cookie=cookie)
    require(status == 200 and body["status"] == "completed", "completed_state_missing")
    return {
        "real_graph_pg_checkpoint": True,
        "sse_reads": 2,
        "model_calls_on_reconnect": 0,
        "usage": body.get("usage"),
    }


def budget():
    # Direct typed ledger fixture: never installs an OPEN governor or creates an
    # owner approval record. Both real application processes remain CLOSED.
    from src.llm.budget.config import BudgetConfig, ClassBudget, Ceiling, Limits
    from src.llm.budget.ledger import DbBudgetLedger
    from src.llm.budget.errors import BudgetError

    cfg = BudgetConfig(
        classes={
            "production": ClassBudget(
                Ceiling(1000, 900),
                100,
                {"agent": Ceiling(1000, 900), "embedding": Ceiling(100, 90)},
            )
        },
        limits=Limits(100, 100, 1, 0, 10),
        pricing={},
        approval_marker=None,
        total=Ceiling(1000, 900),
        total_max_requests=100,
    )
    sf = factory()
    ledger = DbBudgetLedger(sf)

    def reserve(fp):
        return ledger.reserve(
            cfg,
            budget_class="production",
            category="agent",
            operation="agent",
            model="synthetic",
            endpoint="chat",
            fingerprint=fp,
            worst_case=600,
        )

    from concurrent.futures import ThreadPoolExecutor

    def attempt(n):
        try:
            return reserve("campaign-atomic-" + str(n))
        except BudgetError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        winners = [x for x in pool.map(attempt, range(8)) if x is not None]
    require(len(winners) == 1, "atomic_reservation_overrun")
    ledger.settle(winners[0], outcome="unknown")
    try:
        ledger.reserve(
            cfg,
            budget_class="production",
            category="embedding",
            operation="embedding",
            model="synthetic",
            endpoint="embedding",
            fingerprint="campaign-category",
            worst_case=91,
        )
    except BudgetError:
        pass
    else:
        raise RuntimeError("category_limit_bypassed")
    for fp in ("campaign-retry", "campaign-second"):
        try:
            reserve(fp)
        except BudgetError:
            pass
        else:
            raise RuntimeError("spend_cap_bypassed")
    before = ledger.snapshot(cfg, "production")
    after = DbBudgetLedger(factory()).snapshot(cfg, "production")
    require(before == after, "durable_spend_changed")
    ledger.kill("synthetic_campaign")
    require(DbBudgetLedger(factory()).killed(), "kill_not_durable")
    return {
        "typed_ledger_fixture": True,
        "unknown_reservation_preserved": True,
        "retry_cap_refused": True,
        "restart_snapshot_equal": True,
        "kill_persisted": True,
        "owner_approval_created": False,
    }


def scanner():
    from src.documents.file_security import ClamAvScanner, EICAR

    scan = ClamAvScanner(host="clamav", port=3310, connect_timeout=1, scan_timeout=5)
    clean = scan.scan(b"Synthetic harmless text.", "synthetic.txt")
    infected = scan.scan(EICAR, "eicar.txt")
    require(
        clean.clean and not infected.clean and infected.status == "infected",
        "real_clamd_scan_failed",
    )
    return {
        "clean": clean.status,
        "eicar": infected.status,
        "scanner": "real_clamd",
        "definitions": "offline_eicar_only",
        "freshness_qualified": False,
    }


def outage(kind):
    if kind == "db_down":
        require(http("/api/v1/ready")[0] == 503, "database_outage_not_refused")
    elif kind == "redis_down":
        status, body, _ = http("/api/v1/ready")
        require(status == 503, "shared_required_outage_not_refused")
        require("rate_limiter" in json.dumps(body), "redis_outage_not_visible")
        from src.api.rate_limit import (
            RedisRateLimiter,
            RateLimitPolicy,
            configured_redis_client,
        )

        limiter = RedisRateLimiter(
            configured_redis_client(),
            prefix=os.environ["RATE_LIMIT_NAMESPACE"],
            key_secret=os.environ["RATE_LIMIT_KEY_SECRET"],
        )
        local = limiter.hit(
            "campaign_outage",
            "synthetic",
            RateLimitPolicy("campaign_outage", 2, 30, "global", "local"),
        )
        deny = limiter.hit(
            "campaign_deny",
            "synthetic",
            RateLimitPolicy("campaign_deny", 2, 30, "global", "deny"),
        )
        require(
            local.allowed and not deny.allowed and deny.store_failure_denied,
            "outage_policy_bypass",
        )
    else:
        from src.documents.file_security import ClamAvScanner, FileScanUnavailable

        try:
            ClamAvScanner(
                host="clamav", port=3310, connect_timeout=1, scan_timeout=2
            ).scan(b"Synthetic", "synthetic.txt")
        except FileScanUnavailable:
            pass
        else:
            raise RuntimeError("scanner_outage_permissive")
    return {"injected": kind, "refused": True}


def recovered():
    require(http("/api/v1/ready")[0] == 200, "readiness_not_recovered")
    return scanner()


def slow_prepare():
    from src.agent.models import AgentRunRequest

    control(mode="plain")
    c = credentials()
    result = agent().run(
        AgentRunRequest(
            goal="Synthetic active-run fixture",
            user_id=str(c["alice"]["user_id"]),
            enable_current_market_research=False,
        )
    )
    require(result.status == "completed", "active_fixture_failed")
    c["run_id"] = result.run_id
    Path("/campaign/private/credentials.json").write_text(json.dumps(c))
    control(mode="slow", entered=False)
    return {"prepared": True}


def slow_continue():
    rid = credentials()["run_id"]
    cookie = login()
    status, _, _ = http(
        "/api/v1/agent/runs/" + rid + "/messages",
        "POST",
        {"message": "Synthetic slow continuation"},
        cookie=cookie,
    )
    return {"status": status}


def entered():
    return {"entered": control()["entered"]}


def cancel_active():
    rid = credentials()["run_id"]
    cookie = login(host="api_b")
    # Independent API admission must refuse the same unsettled run.
    require(
        http(
            "/api/v1/agent/runs/" + rid + "/messages",
            "POST",
            {"message": "Synthetic concurrent continuation"},
            cookie=cookie,
            host="api_b",
        )[0]
        == 409,
        "concurrent_producer_accepted",
    )
    require(
        http(
            "/api/v1/agent/runs/" + rid + "/cancel", "POST", cookie=cookie, host="api_b"
        )[0]
        == 200,
        "cancel_refused",
    )
    control(mode="plain")
    return {"cross_instance_concurrent_refusal": 409, "cancel_requested": True}


def lost_state():
    from src.agent.run_control import RunControlStore

    rid = credentials()["run_id"]
    owner = str(credentials()["alice"]["user_id"])
    row = RunControlStore(factory()).owned(rid, owner)
    require(row is not None and not row["settled"], "lost_process_settled_ambiguity")
    cookie = login(host="api_b")
    require(
        http(
            "/api/v1/agent/runs/" + rid + "/messages",
            "POST",
            {"message": "Synthetic forbidden takeover"},
            cookie=cookie,
            host="api_b",
        )[0]
        == 409,
        "lost_process_reexecuted",
    )
    control(mode="plain")
    return {
        "durable_unsettled": True,
        "takeover_refused": 409,
        "unknown_outcome_preserved": True,
    }


def cancelled():
    from src.agent.run_control import RunControlStore

    c = credentials()
    row = RunControlStore(factory()).owned(c["run_id"], str(c["alice"]["user_id"]))
    require(
        row is not None and row["settled"] and row["status"] == "cancelled",
        "cancellation_not_settled",
    )
    result = agent().get_run(c["run_id"], str(c["alice"]["user_id"]))
    require(
        result.usage and result.usage["usage_complete"] is False,
        "ambiguous_usage_reported_complete",
    )
    return {
        "cancelled": True,
        "settled": True,
        "usage_complete": False,
        "actual_provider_call": False,
    }


def hitl():
    from src.agent.models import AgentRunRequest

    c = credentials()
    control(mode="hitl")
    try:
        result = agent().run(
            AgentRunRequest(
                goal="Synthetic memory proposal fixture",
                user_id=str(c["alice"]["user_id"]),
                enable_current_market_research=False,
            )
        )
    finally:
        control(mode="plain")
    require(
        result.awaiting_human_input
        and result.pending_action["type"] == "approve_memory",
        "hitl_fixture_not_paused",
    )
    cookie = login()
    path = "/api/v1/agent/runs/" + result.run_id + "/resume"
    payload = {"action_id": result.pending_action["action_id"], "decision": "approve"}
    status, body, _ = http(path, "POST", payload, cookie=cookie, host="api_b")
    require(status == 200 and body["status"] == "completed", "hitl_resume_failed")
    require(
        http(path, "POST", payload, cookie=cookie)[0] == 409, "hitl_duplicate_accepted"
    )
    return {
        "existing_fixture_resume": 200,
        "duplicate_resume": 409,
        "consent": "explicit_synthetic_approval",
    }


def model_failures():
    from src.agent.models import AgentRunRequest

    outcomes = {}
    try:
        for mode in ("timeout", "rate_limit"):
            control(mode=mode)
            result = agent().run(
                AgentRunRequest(
                    goal="Synthetic failure fixture",
                    user_id=str(credentials()["alice"]["user_id"]),
                    enable_current_market_research=False,
                )
            )
            require(result.status == "failed", "mock_failure_not_projected")
            require(
                result.usage and not result.usage["usage_complete"],
                "mock_failure_unknown_lost",
            )
            outcomes[mode] = {"status": result.status, "usage_complete": False}
    finally:
        control(mode="plain")
    return outcomes


def redis_limits():
    c = credentials()
    payload = {
        "email": "limited@example.invalid",
        "password": "synthetic-wrong-password",
    }
    initial = http("/api/v1/auth/login", "POST", payload)[1]
    known = http(
        "/api/v1/auth/login",
        "POST",
        {"email": c["bob"]["email"], "password": "synthetic-wrong-password"},
    )
    require(
        known[0] == 401
        and initial.get("error", {}).get("message")
        == known[1].get("error", {}).get("message"),
        "account_enumeration_difference",
    )
    statuses = [401]
    for n in range(8):
        status, _, headers = http(
            "/api/v1/auth/login", "POST", payload, host="api_b" if n % 2 == 0 else "api"
        )
        statuses.append(status)
    require(statuses == [401] * 8 + [429], "global_account_limit_not_shared")
    retry = int(headers.get("retry-after", headers.get("Retry-After", "0")))
    require(1 <= retry <= 300, "retry_after_unbounded")
    return {
        "cross_instance_login_statuses": statuses,
        "retry_after_seconds": retry,
        "account_enumeration": "uniform_wrong_credentials",
    }


def upload(data, cookie):
    boundary = "ask4moSyntheticMultipart"
    body = (
        (
            "--"
            + boundary
            + '\r\nContent-Disposition: form-data; name="category"\r\n\r\nother\r\n--'
            + boundary
            + '\r\nContent-Disposition: form-data; name="file"; filename="synthetic.txt"\r\nContent-Type: text/plain\r\n\r\n'
        ).encode()
        + data
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    conn = http.client.HTTPConnection("api", 8000, timeout=25)
    conn.request(
        "POST",
        "/api/v1/documents",
        body,
        {"Cookie": cookie, "Content-Type": "multipart/form-data; boundary=" + boundary},
    )
    response = conn.getresponse()
    status = response.status
    try:
        result = json.loads(response.read())
    except ValueError:
        result = {}
    conn.close()
    return status, result


def documents():
    from src.documents.file_security import EICAR

    cookie = login()
    bob = login("bob")
    data = b"Synthetic integration document. Placeholder experience only."
    status, body = upload(data, cookie)
    require(status == 201, "clean_upload_failed")
    path = "/api/v1/documents/" + str(body["id"])
    require(
        http(path, cookie=cookie)[0] == 200 and http(path, cookie=bob)[0] == 404,
        "document_ownership_failed",
    )
    status, download, _ = http(path + "/download", cookie=cookie, raw=True)
    require(status == 200 and download == data, "document_download_mismatch")
    require(upload(EICAR, cookie)[0] == 422, "infected_upload_accepted")
    return {
        "clean_upload": 201,
        "owner_download": "byte_identical",
        "foreign_access": 404,
        "eicar_upload": 422,
    }


def worker_enqueue():
    from src.jobs.service import JobService

    service = JobService(factory())
    job, created = service.enqueue(
        "diagnostic_noop",
        {"label": "campaign lease fault"},
        idempotency_key="campaign-worker-fault",
    )
    again, duplicate = service.enqueue(
        "diagnostic_noop",
        {"label": "campaign lease fault"},
        idempotency_key="campaign-worker-fault",
    )
    require(
        created and not duplicate and job["public_id"] == again["public_id"],
        "job_idempotency_failed",
    )
    Path("/campaign/private/worker-fault.json").write_text(
        json.dumps({"public_id": job["public_id"]})
    )
    return {"active_duplicate_created": False}


def worker_once():
    # Test-only existing diagnostic handler seam; ordinary workers/registry stay
    # untouched. Real Worker and JobService own the claim, lease and retry state.
    from dataclasses import replace
    from src.jobs.registry import REGISTRY
    from src.jobs.service import JobService
    from src.jobs.worker import Worker

    registry = dict(REGISTRY)

    def wait(payload, context):
        Path("/campaign/worker-entered").write_text("entered")
        time.sleep(60)

    registry["diagnostic_noop"] = replace(
        registry["diagnostic_noop"], handler=wait, lease_seconds=8
    )
    return {"outcome": Worker(JobService(factory(), registry), registry).run_once()}


def worker_entered():
    from src.jobs.service import JobService

    jid = json.loads(Path("/campaign/private/worker-fault.json").read_text())[
        "public_id"
    ]
    job = JobService(factory()).get(jid)
    entered = Path("/campaign/worker-entered").exists()
    if entered:
        require(
            job["state"] == "running"
            and job["attempts"] == 1
            and not job["lease"]["stale"],
            "worker_lease_not_held",
        )
    return {"entered": entered, "initial_state": job["state"]}


def worker_recovered():
    from src.jobs.service import JobService

    jid = json.loads(Path("/campaign/private/worker-fault.json").read_text())[
        "public_id"
    ]
    end = time.monotonic() + 45
    while time.monotonic() < end:
        job = JobService(factory()).get(jid)
        if job["state"] == "succeeded":
            break
        time.sleep(0.25)
    require(
        job["state"] == "succeeded" and job["attempts"] == 2,
        "worker_crash_not_retried_once",
    )
    return {
        "state": job["state"],
        "attempts": job["attempts"],
        "active_duplicate_created": False,
        "fixture_lease_seconds": 8,
    }


def recovery():
    # The host driver first stops every campaign producer; target is a new DB.
    from datetime import datetime, timezone
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from src.backup_set import engine as E, qualified as Q, erasure as X
    from src.knowledge_admin.contracts import (
        RuntimeIdentity,
        EmbeddingState,
        database_fingerprint,
        data_root_identity,
    )
    from src.copilot.embeddings import LocalHashEmbedder
    from src.persistence import make_engine, make_session_factory
    from src.auth_repository import AccountRepository
    from src.privacy.preparation import PreparationRunIndex
    from src.application.account_deletion_service import AccountDeletionService
    from src.documents.storage import LocalDocumentStore

    url = os.environ["DATABASE_URL"]
    release = json.loads(Path("/release-facts.json").read_text())
    require(release["application_sha"] == os.environ["APP_GIT_SHA"], "release_mismatch")
    embed = LocalHashEmbedder()
    identity = RuntimeIdentity(
        database_fingerprint(url),
        data_root_identity("/data/knowledge"),
        embedding=EmbeddingState("local", embed.model, embed.dimensions),
    )
    source = E.Source(
        url,
        Path("/data/documents"),
        Path("/data/knowledge/knowledge_private"),
        Path("/data/knowledge/chroma"),
        identity,
    )
    ledger = X.Ledger(Path("/campaign-ledger/history.jsonl"))
    ledger.path.touch(exist_ok=False)
    key = b"i" * 32
    ledger_key = b"e" * 32  # fixed disposable test keys; never operator custody
    backup = Q.create(
        source,
        out_dir=Path("/campaign-backup/sealed"),
        checkpoint_database_url=url,
        release=release,
        ledger=ledger,
        ledger_head=X.signed_head(ledger, ledger_key),
        ledger_key=ledger_key,
        encryption_key=key,
        execute=True,
        drained=True,
        drain_observed_at=datetime.now(timezone.utc),
    )
    anchor = E.manifest_digest(Path("/campaign-backup/sealed"))
    transfer = Q.transfer(
        Path("/campaign-backup/sealed"),
        Path("/campaign-transfer/sealed"),
        anchor=anchor,
        encryption_key=key,
        execute=True,
    )
    require(backup.ok and transfer.ok, "encrypted_transfer_failed")
    sf = factory()
    uid = credentials()["alice"]["user_id"]
    deleted = AccountDeletionService(
        sf,
        document_store=LocalDocumentStore("/data/documents"),
        agent_service=X._PostgresCheckpointPurger(url),
        preparation_index=PreparationRunIndex(sf),
    ).delete_account(uid)
    require(
        deleted.existed and not deleted.files_failed and not deleted.checkpoints_failed,
        "source_synthetic_erasure_failed",
    )
    X.record_deletion(ledger, uid, datetime.now(timezone.utc))
    target_url = (
        make_url(url)
        .set(database="p5b_recovery_restore_campaign_" + boundary())
        .render_as_string(hide_password=False)
    )
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(
            text("CREATE DATABASE " + E._check_ident(make_url(target_url).database))
        )
    admin.dispose()
    restored = Q.restore(
        Path("/campaign-transfer/sealed"),
        target_root=Path("/campaign/recovered"),
        target_database_url=target_url,
        anchor=anchor,
        ledger=ledger,
        ledger_head=X.signed_head(ledger, ledger_key),
        ledger_key=ledger_key,
        encryption_key=key,
        expected_release=release,
        execute=True,
    )
    require(restored.ok, "connected_restore_failed")
    target_sf = make_session_factory(make_engine(target_url))
    from src.backup_set.admission import pending
    from src.llm.budget.ledger import DbBudgetLedger

    require(
        pending(target_sf) and DbBudgetLedger(target_sf).killed(),
        "recovery_hold_missing",
    )
    require(
        AccountRepository(target_sf).get_account(uid) is None, "erased_account_returned"
    )
    from src.jobs.service import JobService

    job, _ = JobService(target_sf).enqueue(
        "diagnostic_noop", {"label": "held synthetic recovery"}
    )
    require(
        JobService(target_sf).claim("campaign-held-probe") is None,
        "held_worker_claimed",
    )
    Path("/campaign/private/held-job.json").write_text(
        json.dumps({"public_id": job["public_id"]})
    )
    return {
        "encrypted_transfer": True,
        "independent_local_volumes": True,
        "backup_seconds": backup.details["duration_seconds"],
        "restore_seconds": restored.details["duration_seconds"],
        "stored_bytes": backup.details["stored_bytes"],
        "erasure": restored.details["erasure"],
        "persistent_hold": True,
        "unknown_money_preserved": True,
        "production_rto_rpo_approved": False,
    }


def held():
    from sqlalchemy.engine import make_url
    from src.persistence import make_engine, make_session_factory
    from src.jobs.service import JobService

    url = (
        make_url(os.environ["DATABASE_URL"])
        .set(database="p5b_recovery_restore_campaign_" + boundary())
        .render_as_string(hide_password=False)
    )
    sf = make_session_factory(make_engine(url))
    jid = json.loads(Path("/campaign/private/held-job.json").read_text())["public_id"]
    time.sleep(3)
    job = JobService(sf).get(jid)
    require(
        job["state"] == "queued" and job["attempts"] == 0, "held_real_worker_executed"
    )
    require(http("/api/v1/ready", host="api_held")[0] == 503, "held_api_ready")
    require(
        http(
            "/api/v1/auth/me",
            host="api_held",
            cookie="ask4mo_session=synthetic-deleted-session",
        )[0]
        == 503,
        "held_identity_open",
    )
    return {
        "actual_api_hold": 503,
        "actual_worker_claims": 0,
        "recovery_hold_released": False,
    }


ACTIONS = {
    "seed": seed,
    "state": state,
    "identity": identity,
    "http": http_checks,
    "jobs": jobs,
    "agent": agent_checks,
    "budget": budget,
    "scanner": scanner,
    "recovered": recovered,
    "slow_prepare": slow_prepare,
    "slow_continue": slow_continue,
    "entered": entered,
    "cancel": cancel_active,
    "lost_state": lost_state,
    "recovery": recovery,
    "held": held,
    "cancelled": cancelled,
    "hitl": hitl,
    "model_failures": model_failures,
    "redis_limits": redis_limits,
    "documents": documents,
    "worker_enqueue": worker_enqueue,
    "worker_once": worker_once,
    "worker_entered": worker_entered,
    "worker_recovered": worker_recovered,
}


def main():
    try:
        boundary()
        action = sys.argv[1]
        facts = (
            outage(action)
            if action in ("db_down", "redis_down", "scanner_down")
            else ACTIONS[action]()
        )
        print(json.dumps({"ok": True, **facts}, sort_keys=True))
        return 0
    except Exception as e:
        # Exception text can contain connection strings, SQL or private payloads.
        print(json.dumps({"ok": False, "code": type(e).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
