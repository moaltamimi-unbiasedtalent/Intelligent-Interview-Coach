"""05A: the staging Compose topology as code, its readiness additions and its configuration guards.

Fully offline: the Compose file is PARSED (no docker, no `compose up`, no network), the shell scripts are only syntax-checked,
and the readiness probes run against a temp SQLite store. No provider is contacted and nothing is deployed."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "docker-compose.staging.yml"
ENV_EXAMPLE = ROOT / "deploy" / ".env.staging.example"
EXPECTED_SERVICES = {"db", "migrate", "api", "worker", "web", "caddy", "clamav"}


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _env(service: dict) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    return {k: str(v) for k, v in env.items()}


def _volume_targets(service: dict, volume: str) -> list[str]:
    return [v.split(":")[1] for v in service.get("volumes", []) if v.split(":")[0] == volume]


# --- Compose structure ------------------------------------------------------------------------


def test_services_are_exactly_the_expected_set(compose):
    assert set(compose["services"]) == EXPECTED_SERVICES


def test_worker_runs_the_job_worker_from_the_api_image_single_replica(compose):
    api, worker = compose["services"]["api"], compose["services"]["worker"]
    assert worker["command"] == ["python", "-m", "src.jobs.worker"]
    assert worker["build"] == api["build"]                      # same image/Dockerfile as the api
    assert worker["restart"] == "unless-stopped"
    assert "ports" not in worker and "expose" not in worker
    assert "replicas" not in (worker.get("deploy") or {}) and "scale" not in worker   # single replica
    assert ".env.staging" in worker["env_file"] and ".env.staging" in api["env_file"]   # same DATABASE_URL source


def test_worker_waits_for_migrate_and_a_healthy_db(compose):
    deps = compose["services"]["worker"]["depends_on"]
    assert deps["migrate"]["condition"] == "service_completed_successfully"
    assert deps["db"]["condition"] == "service_healthy"
    assert deps["clamav"]["condition"] == "service_healthy"


def test_api_and_worker_share_the_data_root_and_the_knowledge_volume(compose):
    api, worker = compose["services"]["api"], compose["services"]["worker"]
    api_env, worker_env = _env(api), _env(worker)
    assert api_env["COPILOT_DATA_DIR"] == worker_env["COPILOT_DATA_DIR"] == "/data/knowledge"
    assert _volume_targets(api, "knowledge-data") == _volume_targets(worker, "knowledge-data") == [api_env["COPILOT_DATA_DIR"]]
    # the private documents volume is available to BOTH and mounted at the same path
    assert _volume_targets(api, "documents") == _volume_targets(worker, "documents") == ["/data/documents"]
    # no other service mounts the knowledge or documents data
    for name, svc in compose["services"].items():
        if name not in ("api", "worker"):
            assert not _volume_targets(svc, "knowledge-data") and not _volume_targets(svc, "documents"), name


def test_data_root_is_pinned_in_compose_not_only_in_env_file(compose):
    # compose `environment` overrides env_file, so a stale .env.staging value cannot split the api and worker.
    for name in ("api", "worker"):
        assert _env(compose["services"][name])["COPILOT_DATA_DIR"]


def test_clamav_is_internal_only_and_wired_to_api_and_worker(compose):
    clam = compose["services"]["clamav"]
    assert clam["image"].startswith("clamav/clamav")
    assert "ports" not in clam                                   # never published to the host
    assert [str(p) for p in clam["expose"]] == ["3310"]
    assert _volume_targets(clam, "clamav-signatures") == ["/var/lib/clamav"]
    assert "healthcheck" in clam
    for name in ("api", "worker"):
        env = _env(compose["services"][name])
        assert env["FILE_SCAN_PROVIDER"] == "clamav" and env["CLAMAV_HOST"] == "clamav" and env["CLAMAV_PORT"] == "3310"
    # only the edge proxy publishes ports
    assert [n for n, s in compose["services"].items() if "ports" in s] == ["caddy"]


def test_healthchecks_present_and_api_uses_the_readiness_path(compose):
    for name in ("db", "api", "worker", "web", "clamav"):
        assert "healthcheck" in compose["services"][name], name
    api_test = " ".join(compose["services"]["api"]["healthcheck"]["test"])
    assert "/api/v1/ready" in api_test
    worker_test = compose["services"]["worker"]["healthcheck"]["test"]
    assert "src.jobs.healthcheck" in " ".join(worker_test)


def test_named_volumes_are_declared_and_all_referenced(compose):
    declared = set(compose["volumes"])
    assert {"db-data", "documents", "knowledge-data", "clamav-signatures", "caddy-data", "caddy-config"} <= declared
    used = {v.split(":")[0] for s in compose["services"].values() for v in s.get("volumes", []) if not v.startswith(".")}
    assert used == declared                                      # nothing declared-but-unused or used-but-undeclared


def test_every_app_service_depends_on_migration_before_starting(compose):
    for name in ("api", "worker"):
        assert compose["services"][name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert compose["services"]["migrate"]["restart"] == "no"


# --- No secrets / env example ----------------------------------------------------------------


def _assignments(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def test_env_example_has_the_topology_settings_and_only_placeholders():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    a = _assignments(text)
    assert a["COPILOT_DATA_DIR"] == "/data/knowledge"
    assert a["FILE_SCAN_PROVIDER"] == "clamav" and a["CLAMAV_HOST"] == "clamav" and a["CLAMAV_PORT"] == "3310"
    assert a["MALWARE_SCAN_REQUIRED"] == "true"
    assert "JOB_WORKER_POLL_SECONDS" in a
    assert a["COPILOT_EMBEDDING_API_KEY"] == ""
    assert "MUST NOT RELY ON THE HASH" in text and "REVIEW-04" in text
    for key, value in a.items():
        if any(w in key for w in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
            assert value == "" or (value.startswith("<") and value.endswith(">")), f"{key} is not a placeholder"
    assert not re.search(r"sk-[A-Za-z0-9_-]{12,}|xkeysib-|AKIA[0-9A-Z]{12,}", text)


def test_compose_contains_no_real_secret_values():
    text = COMPOSE.read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9_-]{12,}|xkeysib-|AKIA[0-9A-Z]{12,}|postgresql\+psycopg://[^$\s]+:[^$\s]+@", text)
    assert "POSTGRES_PASSWORD:?" in text                          # required from the untracked env file, no default


def test_compose_states_the_deployment_freeze():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "DEPLOYMENT FREEZE" in text and "OD-HOSTED" in text
    readme = (ROOT / "deploy" / "README-staging.md").read_text(encoding="utf-8")
    assert "DEPLOYMENT FREEZE" in readme and "OD-HOSTED" in readme and "NOT VALIDATED" in readme.upper()


# --- Backup / restore scripts ----------------------------------------------------------------


@pytest.mark.parametrize("script", ["backup.sh", "restore.sh", "migrate.sh"])
def test_deploy_scripts_have_valid_shell_syntax(script):
    r = subprocess.run(["bash", "-n", str(ROOT / "deploy" / "scripts" / script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_backup_and_restore_cover_db_documents_and_knowledge():
    backup = (ROOT / "deploy/scripts/backup.sh").read_text(encoding="utf-8")
    restore = (ROOT / "deploy/scripts/restore.sh").read_text(encoding="utf-8")
    for needle in ("pg_dump", "DOCUMENT_STORAGE_DIR", "COPILOT_DATA_DIR", "ask4mo-knowledge-"):
        assert needle in backup, needle
    for needle in ("pg_restore", "DOCS_TAR", "KNOWLEDGE_TAR", "COPILOT_DATA_DIR"):
        assert needle in restore, needle


def test_backup_then_restore_roundtrip_of_the_data_volumes(tmp_path):
    """Run only the tar halves of the scripts (pg_dump/pg_restore are stubbed): proves the knowledge dir is archived and restorable."""
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "pg_dump").write_text('#!/usr/bin/env bash\nfor a in "$@"; do case "$a" in --file=*) : > "${a#--file=}";; esac; done\n')
    (stub / "pg_restore").write_text("#!/usr/bin/env bash\nexit 0\n")
    for f in stub.iterdir():
        f.chmod(0o755)
    docs, know, out = tmp_path / "documents", tmp_path / "knowledge", tmp_path / "backups"
    docs.mkdir()
    know.mkdir()
    (docs / "d.txt").write_text("doc")
    (know / "k.txt").write_text("kb")
    import os

    env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}", "DATABASE_URL": "postgresql://u:p@h/ask4mo_staging",
           "DOCUMENT_STORAGE_DIR": str(docs), "COPILOT_DATA_DIR": str(know), "BACKUP_DIR": str(out)}
    r = subprocess.run(["bash", str(ROOT / "deploy/scripts/backup.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    ktar = next(out.glob("ask4mo-knowledge-*.tar.gz"))
    dtar = next(out.glob("ask4mo-documents-*.tar.gz"))
    dump = next(out.glob("ask4mo-db-*.dump"))
    docs2, know2 = tmp_path / "r" / "documents", tmp_path / "r" / "knowledge"
    renv = {**os.environ, "PATH": env["PATH"], "TARGET_DATABASE_URL": "postgresql://u:p@h/ask4mo_restore", "DB_DUMP": str(dump),
            "DOCS_TAR": str(dtar), "DOCUMENT_STORAGE_DIR": str(docs2), "KNOWLEDGE_TAR": str(ktar), "COPILOT_DATA_DIR": str(know2)}
    r = subprocess.run(["bash", str(ROOT / "deploy/scripts/restore.sh")], env=renv, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (know2 / "k.txt").read_text() == "kb" and (docs2 / "d.txt").read_text() == "doc"


# --- Config guard: the fake scanner is refused in hosted environments --------------------------


def _hosted_env(monkeypatch, env: str, **extra):
    for k in ("FILE_SCAN_PROVIDER", "COPILOT_DATA_DIR", "DOCUMENT_STORAGE_DIR", "PAUSED_CAPABILITIES"):
        monkeypatch.delenv(k, raising=False)
    base = {"FRONTEND_ORIGINS": "https://app.example.com", "DATABASE_URL": "postgresql+psycopg://u:p@db/app",
            "APP_BASE_URL": "https://app.example.com", "OPENROUTER_API_KEY": "x", "EMAIL_PROVIDER": "brevo",
            "BREVO_API_KEY": "x", "EMAIL_SENDER": "no-reply@example.com"}
    for k, v in {**base, **extra}.items():
        monkeypatch.setenv(k, v)
    from src.api.env_validation import validate_runtime_config

    return validate_runtime_config(env)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_hosted_environments_refuse_the_fake_scanner(monkeypatch, env):
    report = _hosted_env(monkeypatch, env, FILE_SCAN_PROVIDER="fake")
    assert not report.ok and any("FILE_SCAN_PROVIDER=fake" in c for c in report.critical)


def test_enforce_runtime_config_raises_for_fake_scanner_in_staging(monkeypatch):
    _hosted_env(monkeypatch, "staging", FILE_SCAN_PROVIDER="fake")
    monkeypatch.setenv("API_ENV", "staging")
    from src.api.env_validation import enforce_runtime_config

    with pytest.raises(RuntimeError, match="FILE_SCAN_PROVIDER=fake"):
        enforce_runtime_config()


def test_clamav_passes_and_missing_provider_or_data_root_only_warn(monkeypatch):
    ok = _hosted_env(monkeypatch, "staging", FILE_SCAN_PROVIDER="clamav", COPILOT_DATA_DIR="/data/knowledge")
    assert ok.ok and not any("FILE_SCAN_PROVIDER" in w or "COPILOT_DATA_DIR" in w for w in ok.warnings)
    bare = _hosted_env(monkeypatch, "staging")
    assert bare.ok
    assert any("FILE_SCAN_PROVIDER" in w for w in bare.warnings) and any("COPILOT_DATA_DIR" in w for w in bare.warnings)


def test_dev_and_test_may_still_use_the_fake_scanner(monkeypatch):
    for env in ("development", "test"):
        assert _hosted_env(monkeypatch, env, FILE_SCAN_PROVIDER="fake").ok


# --- Readiness probes -------------------------------------------------------------------------


@pytest.fixture()
def sf(tmp_path):
    from src.persistence import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{tmp_path / 'r.db'}")
    init_db(engine, force=True)
    yield make_session_factory(engine)
    engine.dispose()


def test_worker_heartbeat_fresh_and_stale(sf):
    from src.application.hosted_readiness import worker_heartbeat_fresh, worker_status
    from src.jobs.service import JobService

    assert worker_heartbeat_fresh(sf) is False and worker_status(sf) == "stale"      # no worker has ever reported
    now = datetime.now(timezone.utc)
    svc = JobService(sf)
    svc.touch_worker("w1", now=now - timedelta(seconds=120))
    assert worker_heartbeat_fresh(sf, max_age_seconds=60) is False
    assert worker_heartbeat_fresh(sf, max_age_seconds=180) is True                    # the container healthcheck window
    svc.touch_worker("w2", now=now)
    assert worker_heartbeat_fresh(sf) is True and worker_status(sf) == "ok"
    svc.touch_worker("w2", now=now, status="stopped")
    svc.touch_worker("w1", now=now - timedelta(seconds=400))
    assert worker_heartbeat_fresh(sf, max_age_seconds=180) is False                   # stopped workers never count


def test_worker_status_unknown_when_store_unreadable():
    from src.application.hosted_readiness import worker_status

    def broken():
        raise RuntimeError("db down")

    assert worker_status(broken) == "unknown"


def test_data_root_writable_reports_booleans_only(monkeypatch, tmp_path):
    from src.application.hosted_readiness import data_root_writable

    root = tmp_path / "knowledge"
    monkeypatch.setenv("COPILOT_DATA_DIR", str(root))
    assert data_root_writable() is True and root.is_dir() and not list(root.iterdir())    # probe file removed
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("COPILOT_DATA_DIR", str(blocker / "sub"))                           # cannot be created under a file
    assert data_root_writable() is False


def test_scanner_status_never_reports_fake_or_unset_as_reachable(monkeypatch):
    from src.application import hosted_readiness as hr

    monkeypatch.delenv("FILE_SCAN_PROVIDER", raising=False)
    assert hr.scanner_status() == "not_configured"
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "fake")
    assert hr.scanner_status() == "not_configured"
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "clamav")
    monkeypatch.setattr("src.documents.file_security.ClamAvScanner.available", lambda self: True)
    assert hr.scanner_status() == "reachable"
    monkeypatch.setattr("src.documents.file_security.ClamAvScanner.available", lambda self: False)
    assert hr.scanner_status() == "unreachable"


@pytest.fixture()
def ready_client():
    from fastapi.testclient import TestClient

    from src.api.main import create_app

    with TestClient(create_app()) as client:          # the context manager runs the lifespan that builds app resources
        yield client


def test_ready_in_dev_keeps_its_original_shape(ready_client):
    client = ready_client
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    body = r.json()
    assert set(body["checks"]) == {"database", "config"} and "dependencies" not in body


def test_ready_in_a_hosted_env_reports_topology_without_secrets(ready_client, monkeypatch, tmp_path):
    from src.application import hosted_readiness as hr

    client = ready_client
    monkeypatch.setattr(hr, "is_hosted", lambda env=None: True)
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "clamav")
    monkeypatch.setenv("CLAMAV_HOST", "scanner.internal.example")
    monkeypatch.setattr("src.documents.file_security.ClamAvScanner.available", lambda self: False)
    r = client.get("/api/v1/ready")
    assert r.status_code == 200, r.text                         # an absent worker / scanner is reported, not gating
    body = r.json()
    assert body["checks"]["data_root_writable"] is True
    assert body["dependencies"] == {"worker_heartbeat": "stale", "scanner": "unreachable", "rate_limiter": "process_local"}
    dumped = r.text
    assert "scanner.internal.example" not in dumped and str(tmp_path) not in dumped


def test_ready_returns_503_when_the_data_root_is_not_writable(ready_client, monkeypatch, tmp_path):
    from src.application import hosted_readiness as hr

    client = ready_client
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(hr, "is_hosted", lambda env=None: True)
    monkeypatch.setenv("COPILOT_DATA_DIR", str(blocker / "sub"))
    r = client.get("/api/v1/ready")
    assert r.status_code == 503                                  # the safe error envelope hides the detail body
    assert str(tmp_path) not in r.text
