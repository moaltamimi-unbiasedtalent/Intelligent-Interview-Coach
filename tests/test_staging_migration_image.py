"""Real image / disposable PostgreSQL regression, opt in with RUN_MIGRATION_IMAGE_TESTS=1.

Build deploy/Dockerfile.api before running; MIGRATION_TEST_IMAGE selects that build.
No host ports, bind-mounted private state, staging env files or existing DB URLs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest
import yaml

from tests._alembic_head import repository_head

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATION_IMAGE_TESTS") != "1",
    reason="requires explicitly built API image and disposable Docker PostgreSQL",
)


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], text=True, capture_output=True, timeout=240)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture()
def stack(tmp_path_factory):
    root = tmp_path_factory.mktemp("migration-image")
    project = "ask4mo-migration-test-" + uuid.uuid4().hex[:12]
    image = os.environ.get("MIGRATION_TEST_IMAGE", "ask4mo-migration-test:wave4")
    original = yaml.safe_load((ROOT / "deploy/docker-compose.staging.yml").read_text())["services"]
    # Fresh, unexposed DB; no persistent named volume and no real env_file loaded.
    db = {
        "image": original["db"]["image"],
        "environment": {"POSTGRES_USER": "disposable", "POSTGRES_PASSWORD": "synthetic-test-only",
                        "POSTGRES_DB": "disposable_migration"},
        "tmpfs": ["/var/lib/postgresql/data"],
        "healthcheck": {"test": ["CMD-SHELL", "pg_isready -U disposable -d disposable_migration"],
                        "interval": "1s", "timeout": "5s", "retries": 60},
    }
    migration = {"image": image, "restart": original["migrate"]["restart"],
                 "command": original["migrate"]["command"],
                 "depends_on": original["migrate"]["depends_on"],
                 "environment": {"DATABASE_URL": "postgresql+psycopg://disposable:synthetic-test-only@db/disposable_migration",
                                 "ASK4MO_PROVIDER_MODE": "offline", "API_ENV": "test"}}
    services = {"db": db, "migrate": migration}
    for name in ("api", "worker"):
        # Probe startup only; use the real migration dependency, no API/worker execution.
        assert original[name]["depends_on"]["migrate"] == {"condition": "service_completed_successfully"}
        services[name] = {"image": image, "command": ["python", "-c", "print('STARTED')"],
                          "depends_on": {"migrate": original[name]["depends_on"]["migrate"]}}
    compose = root / "compose.yml"
    compose.write_text(yaml.safe_dump({"services": services}))

    def dc(*args, check=True):
        return docker("compose", "-p", project, "-f", str(compose), *args, check=check)

    def sql(statement):
        return dc("exec", "-T", "db", "psql", "-U", "disposable", "-d", "disposable_migration",
                  "-v", "ON_ERROR_STOP=1", "-Atc", statement).stdout.strip()

    try:
        dc("up", "-d", "--wait", "db")
        yield image, services, compose, dc, sql, root
    finally:
        dc("down", "--volumes", "--remove-orphans", check=False)
        docker("image", "rm", project + ":failure", check=False)


def test_built_image_contains_exact_compose_entrypoint_and_nonroot_user(stack):
    image, services, _, _, _, _ = stack
    command = services["migrate"]["command"]
    assert command == ["bash", "scripts/migrate.sh"]
    result = docker("run", "--rm", "--network", "none", image, "python", "-c",
                    "import os,pathlib; assert os.getuid()==10001; "
                    f"assert pathlib.Path({command[1]!r}).is_file(); "
                    "assert pathlib.Path('alembic.ini').is_file()")
    assert result.returncode == 0
    config = json.loads(docker("image", "inspect", image).stdout)[0]["Config"]
    assert config["WorkingDir"] == "/app" and config["User"] == "appuser"
    assert config["Cmd"][0] == "uvicorn" and not config.get("Entrypoint")


def test_exact_command_upgrades_postgresql_twice_without_losing_rows(stack):
    _, _, _, dc, sql, _ = stack
    sql("CREATE TABLE migration_sentinel (id integer PRIMARY KEY, value text NOT NULL); "
        "INSERT INTO migration_sentinel VALUES (1, 'preserve-me')")
    for _ in range(2):
        dc("run", "--rm", "migrate")
        assert sql("SELECT version_num FROM alembic_version") == repository_head()
        assert sql("SELECT value FROM migration_sentinel WHERE id=1") == "preserve-me"
    dc("up", "-d", "api", "worker")
    for name in ("api", "worker"):
        container = dc("ps", "-aq", name).stdout.strip()
        assert docker("wait", container).stdout.strip() == "0"
        assert "STARTED" in dc("logs", name).stdout


def test_failed_upgrade_rolls_back_and_blocks_api_and_worker_startup(stack):
    image, services, compose, dc, sql, root = stack
    # Independent of test order: ensure this disposable DB is at the real head.
    dc("run", "--rm", "migrate")
    sql("CREATE TABLE IF NOT EXISTS failure_sentinel (id integer PRIMARY KEY); "
        "INSERT INTO failure_sentinel VALUES (1) ON CONFLICT DO NOTHING")
    migrations = root / "migrations"
    shutil.copytree(ROOT / "migrations", migrations)
    (migrations / "versions" / "zzzz_failure_probe.py").write_text(
        "from alembic import op\nrevision='zzzz_failure_probe'\n"
        f"down_revision={repository_head()!r}\nbranch_labels=None\ndepends_on=None\n"
        "def upgrade():\n    op.execute('DELETE FROM failure_sentinel')\n"
        "    raise RuntimeError('synthetic upgrade failure')\n"
        "def downgrade():\n    raise RuntimeError('no automatic downgrade')\n")
    # COPY via Docker API also works on local VMs without host temp-dir sharing.
    project = dc("config", "--format", "json")
    fault_image = json.loads(project.stdout)["name"] + ":failure"
    (root / "Dockerfile").write_text(f"FROM {image}\nCOPY --chown=10001:10001 migrations /app/migrations\n")
    docker("build", "-t", fault_image, str(root))
    services["migrate"]["image"] = fault_image
    compose.write_text(yaml.safe_dump({"services": services}))
    failed = dc("up", "-d", "api", "worker", check=False)
    assert failed.returncode != 0
    assert "synthetic upgrade failure" in dc("logs", "migrate").stdout
    assert sql("SELECT version_num FROM alembic_version") == repository_head()
    assert sql("SELECT count(*) FROM failure_sentinel") == "1"
    for name in ("api", "worker"):
        ids = dc("ps", "-aq", name).stdout.split()
        assert len(ids) == 1
        for container in ids:
            state = json.loads(docker("inspect", container).stdout)[0]["State"]
            assert state["Status"] == "created" and state["StartedAt"].startswith("0001-")
        assert "STARTED" not in dc("logs", name).stdout


def test_existing_postgres_mail_attempts_survive_category_constraint_upgrade(stack):
    """Qualify 0048 -> 0049 in the built image without rebuilding the table."""
    _, _, _, dc, sql, _ = stack
    dc('run', '--rm', 'migrate', 'python', '-m', 'alembic', 'upgrade', '0048_agent_run_controls')
    sql("INSERT INTO email_attempts (id,message_type,provider,status,created_at) "
        "VALUES (701,'password_reset','memory','captured',now()); "
        "GRANT SELECT ON email_attempts TO PUBLIC")
    oid = sql("SELECT oid FROM pg_class WHERE oid='email_attempts'::regclass")
    acl = sql("SELECT relacl::text FROM pg_class WHERE oid='email_attempts'::regclass")
    indexes = sql("SELECT string_agg(indexdef, E'\\n' ORDER BY indexname) FROM pg_indexes WHERE tablename='email_attempts'")
    checks = sql("SELECT string_agg(conname || ':' || pg_get_constraintdef(oid), E'\\n' ORDER BY conname) "
                 "FROM pg_constraint WHERE conrelid='email_attempts'::regclass AND conname <> 'ck_email_attempts_type'")
    dc('run', '--rm', 'migrate')
    assert sql('SELECT version_num FROM alembic_version') == repository_head()
    assert sql("SELECT id || ':' || message_type || ':' || status FROM email_attempts WHERE id=701") == '701:password_reset:captured'
    assert sql("SELECT oid FROM pg_class WHERE oid='email_attempts'::regclass") == oid
    assert sql("SELECT relacl::text FROM pg_class WHERE oid='email_attempts'::regclass") == acl
    assert sql("SELECT string_agg(indexdef, E'\\n' ORDER BY indexname) FROM pg_indexes WHERE tablename='email_attempts'") == indexes
    assert sql("SELECT string_agg(conname || ':' || pg_get_constraintdef(oid), E'\\n' ORDER BY conname) "
               "FROM pg_constraint WHERE conrelid='email_attempts'::regclass AND conname <> 'ck_email_attempts_type'") == checks
    for idx, kind in enumerate(('email_verification', 'password_reset', 'account_notice', 'admin_test',
                                'workspace_invitation', 'ownership_transfer'), start=702):
        sql("INSERT INTO email_attempts (id,message_type,provider,status,created_at) "
            f"VALUES ({idx},'{kind}','memory','captured',now())")
    invalid = dc('exec', '-T', 'db', 'psql', '-U', 'disposable', '-d', 'disposable_migration', '-v', 'ON_ERROR_STOP=1',
                 '-c', "INSERT INTO email_attempts (id,message_type,provider,status,created_at) "
                       "VALUES (799,'unknown_kind','memory','captured',now())", check=False)
    assert invalid.returncode != 0
    invalid_status = dc('exec', '-T', 'db', 'psql', '-U', 'disposable', '-d', 'disposable_migration', '-v', 'ON_ERROR_STOP=1',
                        '-c', "INSERT INTO email_attempts (id,message_type,provider,status,created_at) "
                              "VALUES (800,'account_notice','memory','not_a_status',now())", check=False)
    assert invalid_status.returncode != 0
    assert sql('SELECT count(*) FROM email_attempts WHERE id=701') == '1'
