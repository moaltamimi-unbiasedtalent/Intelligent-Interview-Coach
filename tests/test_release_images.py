"""Manifest integrity / conservative promotion policy, no Docker or private stores."""
from contextlib import nullcontext
import json

import pytest
import yaml

from scripts import release_images as R


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    files = {"src/llm/budget/governor.py": "HOSTED_POLICY_VERSION = 2", "src/billing/policy.py": '\n'.join(f'{k} = False' for k in ('LIVE_BILLING_ENABLED', 'EXTERNAL_CHECKOUT_AUTHORIZED', 'STRIPE_WEBHOOK_AUTHORIZED', 'RECONCILE_SCHEDULER_ENABLED', 'PROVIDER_READS_AUTHORIZED', 'PAID_ENTITLEMENT_POLICY_APPROVED')),
             "migrations/versions/0001_base.py": 'revision="0001_base"\ndown_revision=None',
             "migrations/versions/0002_next.py": 'revision="0002_next"\ndown_revision="0001_base"',
             "prompts/agent/v1.txt": "private prompt content is hashed, never emitted",
             "scripts/example.py": "pass", "deploy/scripts/migrate.sh": "alembic upgrade head",
             "deploy/release-policy.json": json.dumps({"version": 1, "minimum_source_sha": R.MINIMUM, "compatible_schema_revisions": ["0002_next"]}),
             "docs/production/execution/language_readiness.json": "{}", "frontend/package.json": "{}", "frontend/package-lock.json": "{}",
             "frontend/next.config.mjs": "export default {}", "frontend/public/image.svg": "asset",
             "deploy/Dockerfile.api": "FROM python:3.11-slim", "deploy/Dockerfile.web": "FROM node:20-slim", ".dockerignore": "**/.env*",
             "README.md": "test", "requirements.txt": "", "pyproject.toml": "", "alembic.ini": "", "deploy/Caddyfile": "example.invalid {}"}
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    base = yaml.safe_load((R.ROOT / "deploy/docker-compose.staging.yml").read_text())
    (root / "deploy/docker-compose.staging.yml").write_text(yaml.safe_dump(base))
    monkeypatch.setattr(R, "committed_source", lambda sha, repo=R.ROOT: nullcontext(root))
    return root


@pytest.fixture
def manifest(source):
    source_record = R.source_record(source, "a" * 40)
    images = {}
    for role, letter, uid in (("application", "b", 10001), ("web", "c", 1000)):
        contents = {"dependencies": [{"name": "example", "version": "1.0"}], "os_dependencies": [{"name": "libc6", "version": "2.4-1"}], "runtime": "3.11.1" if role == "application" else "20.0.0", "uid": uid}
        if role == "web":
            contents["build_id"] = "build_123"
        images[role] = {"image_id": "sha256:" + letter * 64, "registry_digest": None, "platform": "linux/amd64", "docker_created_at": "2026-10-24T00:00:00Z", "contents": contents}
    return {"version": 1, "kind": "local-docker-image-id", "application_sha": "a" * 40,
            "build_started_at": "2026-10-24T00:00:00Z", "public_api_base_url": "https://api.example.invalid/api/v1",
            "source": source_record, "images": images}


def validate(value, *, sha="a" * 40):
    return R.validate_manifest(value, sha, R.digest(R.canonical(value)), verify_images=False)


def state(revision="0002_next", **changes):
    return {"version": 1, "observed_at": R.timestamp(), "schema_revision": revision,
            "unsettled_agent_runs": 0, "active_jobs": 0, "drained": True, "database_identity_sha256": "d" * 64, **changes}


def test_manifest_contains_required_source_provenance_and_no_prompt_content(manifest):
    assert validate(manifest) is manifest
    assert manifest["source"]["prompt_files"] and manifest["source"]["language_activation_sha256"]
    assert "private prompt content" not in json.dumps(manifest)
    assert manifest["source"]["billing_disabled"] is True
    assert "deploy/docker-compose.staging.yml" in manifest["source"]["deployment_files"]


@pytest.mark.parametrize("path", [("application_sha",), ("images",), ("source",), ("images", "web", "image_id"), ("images", "application", "contents", "dependencies")])
def test_missing_manifest_fields_are_refused(manifest, path):
    item = manifest
    for key in path[:-1]:
        item = item[key]
    del item[path[-1]]
    with pytest.raises(R.ReleaseError):
        validate(manifest)


@pytest.mark.parametrize("field,value", [("image_id", "latest"), ("image_id", "sha256:bad"), ("registry_digest", "repo@example:tag"), ("platform", "linux/arm64")])
def test_wrong_digest_or_platform_refused(manifest, field, value):
    manifest["images"]["web"][field] = value
    with pytest.raises(R.ReleaseError):
        validate(manifest)


def test_wrong_sha_or_manifest_anchor_refused(manifest):
    with pytest.raises(R.ReleaseError, match="application_sha_mismatch"):
        validate(manifest, sha="d" * 40)
    with pytest.raises(R.ReleaseError, match="manifest_anchor_mismatch"):
        R.validate_manifest(manifest, "a" * 40, "e" * 64, verify_images=False)


@pytest.mark.parametrize("change", ["prompt", "activation", "head", "metadata"])
def test_source_fingerprint_and_metadata_cannot_be_rewritten(manifest, change):
    if change == "prompt":
        manifest["source"]["prompt_files"]["prompts/agent/v1.txt"] = "0" * 64
    elif change == "activation":
        manifest["source"]["language_activation_sha256"] = "0" * 64
    elif change == "head":
        manifest["source"]["migration_chain"] = ["future"]
    else:
        manifest["images"]["web"]["contents"]["DATABASE_URL"] = "not permitted"
    with pytest.raises(R.ReleaseError):
        validate(manifest)


@pytest.mark.parametrize("url", ["https://u:p@host/api/v1", "https://host/api/v1?token=private", "https://host/api/v1#private", "http://remote.invalid/api/v1", "https://host/secret", "https://host:bad/api/v1", "https://u%40host/api/v1", "https://host/api/v1\n", "https://host/api/v1?", "https://host/api/v1#"])
def test_public_url_cannot_carry_runtime_secrets(url):
    with pytest.raises(R.ReleaseError):
        R.public_url(url)


def test_missing_disabled_billing_or_changed_policy_requires_review(source):
    (source / "src/billing/policy.py").write_text("LIVE_BILLING_ENABLED=True")
    with pytest.raises(R.ReleaseError, match="billing_not_disabled"):
        R.source_record(source, "a" * 40)


@pytest.mark.parametrize("mode", ["promote", "rollback"])
def test_profiles_keep_image_identity_runtime_and_existing_security(manifest, source, mode):
    base = yaml.safe_load((source / "deploy/docker-compose.staging.yml").read_text())
    profile = R.profile_for(manifest, base, state(), mode, "/runtime/secrets.env", "/reviewed/Caddyfile")
    names = ("api", "worker", "migrate") if mode == "promote" else ("api", "worker")
    for name in (*names, "web"):
        service = profile["services"][name]
        assert "build" not in service and service["pull_policy"] == "never"
        assert service["image"] == manifest["images"]["web" if name == "web" else "application"]["image_id"]
        assert service["environment"]["APP_GIT_SHA"] == "a" * 40
        if name != "web":
            assert service["environment"]["API_ENV"] == "staging"
    assert profile["volumes"] == base["volumes"] and profile["name"] == base["name"]
    assert profile["services"]["worker"]["command"] == ["python", "-m", "src.jobs.worker"]
    assert profile["services"]["api"]["volumes"] == base["services"]["api"]["volumes"]
    if mode == "promote":
        assert profile["services"]["migrate"]["restart"] == "no"
        assert profile["services"]["migrate"]["command"] == ["bash", "scripts/migrate.sh"]
        for name in ("api", "worker"):
            assert profile["services"][name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    else:
        assert "migrate" not in profile["services"]
        assert all("migrate" not in profile["services"][name]["depends_on"] for name in names)
    assert "downgrade" not in yaml.safe_dump(profile)


@pytest.mark.parametrize("revision", ["base", "0001_base", "0049_future", "unknown"])
def test_rollback_to_schema_incompatible_image_is_refused(manifest, revision):
    with pytest.raises(R.ReleaseError, match="rollback_schema_incompatible"):
        R.check_state(state(revision), manifest, "rollback")


@pytest.mark.parametrize("changes", [{"unsettled_agent_runs": 1}, {"active_jobs": 1}, {"drained": False},
                                      {"unsettled_agent_runs": False}, {"observed_at": "2020-01-01T00:00:00Z"}])
def test_active_unsettled_unknown_or_stale_state_is_refused(manifest, changes):
    with pytest.raises(R.ReleaseError):
        R.check_state(state(**changes), manifest, "rollback")


def test_promotion_allows_ordered_upgrade_but_never_newer_unknown_schema(manifest):
    R.check_state(state("base"), manifest, "promote")
    R.check_state(state("0001_base"), manifest, "promote")
    with pytest.raises(R.ReleaseError, match="promotion_schema_incompatible"):
        R.check_state(state("0049_future"), manifest, "promote")


def test_unavailable_or_private_database_target_refused_without_opening(monkeypatch):
    import sqlalchemy
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **kw: pytest.fail("private database must never be opened"))
    for url in ("sqlite:////Volumes/private/development.db", "postgresql://private@production.example.com/app", "postgresql://x@127.0.0.1/real"):
        with pytest.raises(R.ReleaseError):
            R.observe_disposable(url)


def test_readonly_disposable_observation_preserves_unsettled_usage(tmp_path):
    from sqlalchemy import create_engine, text
    path = tmp_path / "disposable.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE alembic_version(version_num text)"))
        c.execute(text("INSERT INTO alembic_version VALUES ('0002_next')"))
        c.execute(text("CREATE TABLE agent_run_controls(settled boolean)"))
        c.execute(text("INSERT INTO agent_run_controls VALUES (false)"))
        c.execute(text("CREATE TABLE jobs(status text)"))
        c.execute(text("INSERT INTO jobs VALUES ('running')"))
    before = R.file_hash(path)
    observed = R.observe_disposable(f"sqlite:///{path}", drained=True)
    assert observed["unsettled_agent_runs"] == observed["active_jobs"] == 1
    assert observed["schema_revision"] == "0002_next"
    assert R.file_hash(path) == before
    engine.dispose()


def test_bad_archive_digest_never_loads_images(manifest, tmp_path, monkeypatch):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(b"not an image")
    monkeypatch.setattr(R, "run", lambda *a, **kw: pytest.fail("untrusted archive must not reach Docker"))
    with pytest.raises(R.ReleaseError, match="archive_digest_mismatch"):
        R.import_images(manifest, "a" * 40, R.digest(R.canonical(manifest)), archive, "0" * 64)


def test_existing_output_is_never_overwritten(tmp_path):
    path = tmp_path / "retained"
    path.mkdir()
    (path / "private").write_text("keep")
    with pytest.raises(R.ReleaseError, match="output_exists"):
        R.new_directory(path)
    assert (path / "private").read_text() == "keep"


def test_duplicate_manifest_fields_are_refused():
    with pytest.raises(R.ReleaseError, match="duplicate_json_key"):
        R.decode_json('{"application_sha":"first","application_sha":"second"}')


def test_database_identity_excludes_credentials_but_not_target():
    first = R.database_identity("postgresql+psycopg://reader:first@127.0.0.1:5432/p5b_test?sslmode=require")
    assert first == R.database_identity("postgresql://writer:second@127.0.0.1/p5b_test")
    assert first != R.database_identity("postgresql://reader:first@127.0.0.1:5432/p5b_other")
    assert "first" not in first and len(first) == 64


def test_current_head_without_controls_is_not_reported_as_zero_unsettled(tmp_path):
    from sqlalchemy import create_engine, text
    path = tmp_path / "malformed-disposable.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE alembic_version(version_num text)"))
        c.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": R.migration_chain(R.ROOT)[-1]})
    before = R.file_hash(path)
    with pytest.raises(R.ReleaseError, match="current_schema_missing_run_controls"):
        R.observe_disposable(f"sqlite:///{path}", drained=True)
    assert R.file_hash(path) == before
    engine.dispose()


def test_database_identity_binds_namespace_options():
    base = "postgresql://reader:secret@127.0.0.1/p5b_test"
    assert R.database_identity(base) != R.database_identity(base + "?options=-csearch_path%3Dother")


def test_cli_driver_failure_is_nonzero_and_does_not_echo_secrets(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("RELEASE_TEST_DATABASE_URL", "synthetic-not-opened")
    def unavailable(*args, **kwargs):
        raise RuntimeError("private-synthetic-driver-detail")
    monkeypatch.setattr(R, "observe_disposable", unavailable)
    assert R.main(["observe-disposable", "--out", str(tmp_path / "state.json")]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {"error": "release_operation_refused"}
    assert "private-synthetic" not in output.out + output.err
    assert not (tmp_path / "state.json").exists()


def test_shared_redis_profile_refuses_an_image_without_the_pinned_client(manifest, tmp_path, monkeypatch):
    monkeypatch.setattr(R, 'validate_manifest', lambda *_a, **_kw: manifest)
    out=tmp_path/'unqualified-plan'
    with pytest.raises(R.ReleaseError, match='release_redis_client_unavailable'):
        R.prepare(manifest,'a'*40,'anchor',state(),'promote',out,'/runtime/private.env',
                  redis_topology='managed',redis_namespace='ask4mo:rl:staging:v2:')
    assert not out.exists()


@pytest.mark.parametrize("capability", [None, 0, 1, 3])
def test_rollback_refuses_image_without_hosted_budget_capability(manifest,source,tmp_path,capability):
    manifest['source']['budget_policy_version']=capability
    with pytest.raises(R.ReleaseError,match='budget_policy_incapable_image'):
        R.profile_for(manifest, yaml.safe_load((source/'deploy/docker-compose.staging.yml').read_text()),state(),'rollback',tmp_path/'private.env',tmp_path/'Caddyfile')
