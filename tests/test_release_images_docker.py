"""Real committed API/web builds, local immutable promotion and offline transfer.

Enabled only with RUN_RELEASE_IMAGE_TESTS=1 and RELEASE_TEST_BUNDLE pointing to
an explicit build made by scripts/release_images.py. Never starts staging.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest
import yaml

from scripts import release_images as R

pytestmark = pytest.mark.skipif(os.environ.get("RUN_RELEASE_IMAGE_TESTS") != "1", reason="requires explicit real API/web image bundle")


@pytest.fixture(scope="module")
def bundle():
    path = Path(os.environ["RELEASE_TEST_BUNDLE"])
    manifest = R.decode_json((path / "release.json").read_text())
    anchor = (path / "release.sha256").read_text().strip()
    sha = os.environ["RELEASE_TEST_SHA"]
    R.validate_manifest(manifest, sha, anchor)
    return manifest, sha, anchor


def test_real_image_provenance_matches_committed_source_and_untracked_files_are_excluded(bundle):
    manifest, sha, anchor = bundle
    R.validate_manifest(manifest, sha, anchor)
    with R.committed_source(sha) as root:
        assert not (root / ".env").exists() and not (root / "frontend/.env.local").exists()
        assert not (root / ".venv").exists() and not (root / "frontend/node_modules").exists()
    for image in manifest["images"].values():
        assert image["registry_digest"] is None
        assert image["contents"]["dependencies"] and image["contents"]["os_dependencies"]
    assert manifest["source"]["billing_disabled"] and manifest["source"]["prompt_files"]
    packages = {d["name"].lower(): d["version"] for d in manifest["images"]["application"]["contents"]["dependencies"]}
    assert packages["redis"] == "8.1.0"


@pytest.mark.parametrize("mode", ["promote", "rollback"])
@pytest.mark.parametrize("topology", [None, "internal", "managed"])
def test_real_compose_resolution_pins_one_application_image_without_builds(bundle, tmp_path, mode, topology):
    manifest, sha, anchor = bundle
    env = tmp_path / "synthetic.env"
    # Deliberately conflicting public metadata/runtime values must be overridden
    # by the verified profile. No private .env is loaded or copied.
    url = f"sqlite:///{tmp_path / 'disposable.db'}"
    env.write_text(f"DATABASE_URL={url}\nPOSTGRES_PASSWORD=synthetic-test-only\nAPI_ENV=development\nAPI_DOMAIN=wrong.invalid\nAPP_GIT_SHA=wrong\nNEXT_PUBLIC_API_BASE_URL=https://wrong.invalid/api/v1\n")
    state = {"version": 1, "observed_at": R.timestamp(), "schema_revision": manifest["source"]["migration_chain"][-1],
             "unsettled_agent_runs": 0, "active_jobs": 0, "drained": True, "database_identity_sha256": R.database_identity(url)}
    namespace = "ask4mo:rl:release-test:"
    password = tmp_path / "synthetic-redis-password"
    password.write_text("synthetic-test-credential-" * 2)
    with env.open("a") as output:
        output.write("RATE_LIMIT_KEY_SECRET=" + "synthetic-test-key-" * 3 + "\n")
        if topology == "managed":
            output.write("REDIS_URL=rediss://limiter:" + "test-credential-" * 3 + "@managed.invalid:6379/0\n")
    options = ({"redis_topology": topology, "redis_namespace": namespace,
                "redis_password_file": str(password) if topology == "internal" else None} if topology else {})
    env_before = R.file_hash(env)
    out = tmp_path / mode
    assert R.prepare(manifest, sha, anchor, state, mode, out, env, **options)["executed"] is False
    assert R.check_compose(manifest, sha, anchor, out / "compose.yml", env, mode, state)["compose_verified"]
    assert R.file_hash(env) == env_before
    original_env = env.read_text()
    try:
        env.write_text(original_env.replace("disposable.db", "other-disposable.db"))
        with pytest.raises(R.ReleaseError, match="runtime_database_identity_mismatch"):
            R.check_compose(manifest, sha, anchor, out / "compose.yml", env, mode, state)
    finally:
        env.write_text(original_env)
    profile = yaml.safe_load((out / "compose.yml").read_text())
    assert profile["services"]["api"]["image"] == profile["services"]["worker"]["image"] == manifest["images"]["application"]["image_id"]
    assert ("migrate" in profile["services"]) is (mode == "promote")
    assert R.file_hash(out / "Caddyfile") == manifest["source"]["deployment_files"]["deploy/Caddyfile"]
    # A different worker build must be refused after actual Compose interpolation.
    profile["services"]["worker"]["image"] = manifest["images"]["web"]["image_id"]
    (out / "tampered.yml").write_text(yaml.safe_dump(profile))
    with pytest.raises(R.ReleaseError, match="prepared_profile_modified"):
        R.check_compose(manifest, sha, anchor, out / "tampered.yml", env, mode, state)
    # Even a modified plan checksum cannot bless a mismatched worker build.
    plan = json.loads((out / "plan.json").read_text())
    plan["compose_sha256"] = R.file_hash(out / "tampered.yml")
    (out / "plan.json").write_text(json.dumps(plan))
    with pytest.raises(R.ReleaseError, match="resolved_image_mismatch"):
        R.check_compose(manifest, sha, anchor, out / "tampered.yml", env, mode, state)


def test_actual_image_identity_and_metadata_cannot_be_substituted(bundle):
    manifest, sha, _ = bundle
    altered = copy.deepcopy(manifest)
    altered["images"]["application"]["image_id"] = manifest["images"]["web"]["image_id"]
    with pytest.raises(R.ReleaseError):
        R.validate_manifest(altered, sha, R.digest(R.canonical(altered)))
    altered = copy.deepcopy(manifest)
    altered["build_started_at"] = "2020-01-01T00:00:00Z"
    with pytest.raises(R.ReleaseError, match="image_metadata_mismatch"):
        R.validate_manifest(altered, sha, R.digest(R.canonical(altered)))


CONTROL_PROBE = r'''
import os, tempfile
os.environ['PYTHON_DOTENV_DISABLED']='1'
os.environ['ASK4MO_PROVIDER_MODE']='offline'
os.environ['API_ENV']='staging'
from src.language_activation import current
from src.billing import policy
assert not policy.LIVE_BILLING_ENABLED and not policy.EXTERNAL_CHECKOUT_AUTHORIZED
assert not current().offered
os.environ['API_ENV']='test'
import asyncio, threading
from langchain_core.messages import AIMessage
from sqlalchemy import select
from src.persistence import Base,User,AIUsageFact,make_engine,make_session_factory
from src.agent.eval import build_eval_career
from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService, RunNotResumableError
from src.privacy.preparation import PreparationRunIndex
class Model:
 def bind_tools(self, schemas):return self
 def invoke(self,messages):return AIMessage(content='Synthetic response.',response_metadata={'cost':0.0009},usage_metadata={'input_tokens':5,'output_tokens':4,'total_tokens':9})
with tempfile.TemporaryDirectory() as directory:
 url='sqlite:///'+directory+'/disposable.sqlite'
 os.environ['DATABASE_URL']=url
 os.environ['COPILOT_DATA_DIR']=directory
 engine=make_engine(url);Base.metadata.create_all(engine);sf=make_session_factory(engine)
 with sf() as s:s.add(User(id=1,subject='synthetic',provider='test'));s.commit()
 def build():return AgentApplicationService(model_factory=lambda:Model(),career_service=build_eval_career(),database_url=url,run_index=PreparationRunIndex(sf),usage_session_factory=sf)
 first,other=build(),build();entered,release=threading.Event(),threading.Event();record=first._record_usage
 def hold(result,owner):
  entered.set();assert release.wait(20);return record(result,owner)
 first._record_usage=hold
 async def check():
  manager=first.streaming();rid=await manager.start(AgentRunRequest(goal='Hello',user_id='1'))
  try:
   assert await asyncio.to_thread(entered.wait,15)
   before=other._snapshot(rid)
   try:other.continue_run(rid,'1','Next')
   except RunNotResumableError:pass
   else:raise AssertionError('unsettled run admitted')
   assert before.values==other._snapshot(rid).values
  finally:
   release.set();await asyncio.gather(*list(manager.tasks))
  result=other.continue_run(rid,'1','Next');assert result.usage['model_calls']==2
  with sf() as s:
   fact=s.scalar(select(AIUsageFact).where(AIUsageFact.usage_key=='agent:'+rid));assert (fact.model_calls,fact.total_tokens,fact.cost_usd_micros)==(2,18,1800)
 asyncio.run(check());engine.dispose()
print('built-image controls, disabled billing and fail-closed languages verified')
'''


def test_built_application_retains_durable_admission_billing_and_language_guards(bundle):
    manifest, _, _ = bundle
    result = R.run(["docker", "run", "--rm", "-i", "--pull", "never", "--network", "none", manifest["images"]["application"]["image_id"],
                    "python", "-c", CONTROL_PROBE], timeout=90)
    assert b"fail-closed languages verified" in result


def test_same_built_api_image_keeps_migration_helper_and_failure_dependencies(bundle, tmp_path):
    manifest, _, _ = bundle
    # Dockerfile FROM needs a named local reference. This unique test alias is
    # verified to the immutable ID; it is never emitted in deployment profiles.
    tag = "ask4mo-release-migration-test:" + uuid.uuid4().hex[:12]
    image_id = manifest["images"]["application"]["image_id"]
    R.run(["docker", "tag", image_id, tag])
    try:
        assert json.loads(R.run(["docker", "image", "inspect", tag]))[0]["Id"] == image_id
        env = {**os.environ, "RUN_MIGRATION_IMAGE_TESTS": "1", "MIGRATION_TEST_IMAGE": tag}
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider", "tests/test_staging_migration_image.py"],
                                cwd=R.ROOT, env=env, capture_output=True, text=True, timeout=300)
        (tmp_path / "migration-test.log").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout[-1600:] + result.stderr[-400:]
        assert "3 passed" in result.stdout
    finally:
        R.run(["docker", "image", "rm", tag])


def test_offline_round_trip_restores_verified_content_ids_without_registry(bundle, tmp_path):
    manifest, sha, anchor = bundle
    transfer = R.export_images(manifest, sha, anchor, tmp_path / "transfer")
    archive = tmp_path / "transfer/images.tar.gz"
    assert R.file_hash(archive) == transfer["archive_sha256"]
    # Remove only the web image just built by this explicitly enabled test,
    # without force. Never remove an unrelated image or any running container.
    web_id = manifest["images"]["web"]["image_id"]
    R.run(["docker", "tag", web_id, "ask4mo-local-web:offline-test-" + uuid.uuid4().hex[:12]])
    tags = json.loads(R.run(["docker", "image", "inspect", web_id]))[0]["RepoTags"]
    assert tags and all(tag.startswith("ask4mo-local-web:") for tag in tags)
    R.run(["docker", "image", "rm", *tags])
    with pytest.raises(R.ReleaseError):
        R.validate_manifest(manifest, sha, anchor)
    assert R.import_images(manifest, sha, anchor, archive, transfer["archive_sha256"])["loaded_and_verified"]
    R.validate_manifest(manifest, sha, anchor)


def test_actual_release_refuses_schema_mismatch_or_unsettled_rollback(bundle, tmp_path):
    manifest, sha, anchor = bundle
    state = {"version": 1, "observed_at": R.timestamp(), "schema_revision": manifest["source"]["migration_chain"][-1],
             "unsettled_agent_runs": 0, "active_jobs": 0, "drained": True, "database_identity_sha256": "d" * 64}
    for index, changes in enumerate(({"schema_revision": "0049_unknown"}, {"schema_revision": "0027_email_attempts"},
                                     {"unsettled_agent_runs": 1}, {"drained": False})):
        target = tmp_path / f"refused-{index}"
        with pytest.raises(R.ReleaseError):
            R.prepare(manifest, sha, anchor, {**state, **changes}, "rollback", target, tmp_path / "not-read.env")
        assert not target.exists()


def test_built_web_default_command_starts_without_host_ports_or_external_network(bundle):
    manifest, _, _ = bundle
    name = "ask4mo-release-web-test-" + uuid.uuid4().hex[:12]
    R.run(["docker", "run", "--rm", "-d", "--pull", "never", "--network", "none", "--name", name, manifest["images"]["web"]["image_id"]])
    try:
        response = None
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            result = subprocess.run(["docker", "exec", name, "curl", "-fsS", "--max-time", "2", "http://127.0.0.1:3000/"], capture_output=True)
            if result.returncode == 0:
                response = result.stdout
                break
            time.sleep(0.3)
        assert response and b"Ask4Mo" in response
        info = json.loads(R.run(["docker", "inspect", name]))[0]
        assert info["Config"]["User"] == "node" and info["HostConfig"]["NetworkMode"] == "none"
    finally:
        R.run(["docker", "stop", "--time", "5", name])


def test_real_image_hosted_budget_boundary_is_closed_without_owner_approval(bundle):
    manifest,sha,anchor=bundle
    script = '''
import json, httpx
from src.llm.budget.governor import install_from_env, HOSTED_POLICY_VERSION
from src.llm.budget.errors import BudgetError
gov=install_from_env(environ={'API_ENV':'staging'})
calls=[]
with httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(1) or httpx.Response(200))) as client:
    for host in ('openrouter.ai','api.openai.com','alternate.invalid'):
        try: client.post('https://'+host+'/v1/chat/completions',json={})
        except BudgetError: pass
        else: raise AssertionError('unguarded inference')
    assert client.get('https://safe.invalid/health').status_code==200
assert calls==[1] and not gov.is_open and HOSTED_POLICY_VERSION==2
print(json.dumps({'hosted_policy_version':2,'paid_attempts_sent':0,'safe_http':True}))
'''
    result=R.run(['docker','run','--rm','--network','none','--entrypoint','python',manifest['images']['application']['image_id'],'-c',script])
    assert json.loads(result)=={'hosted_policy_version':2,'paid_attempts_sent':0,'safe_http':True}


@pytest.mark.parametrize('mode',['promote','rollback'])
def test_real_compose_shares_protected_budget_file_without_creating_approval(bundle,tmp_path,mode):
    manifest,sha,anchor=bundle
    env=tmp_path/'synthetic.env'
    url=f'sqlite:///{tmp_path}/disposable.db'
    env.write_text(f'DATABASE_URL={url}\nPOSTGRES_PASSWORD=synthetic-test-only\nAI_BUDGET_MODE=off\nAI_BUDGET_CLASS=development\n')
    config=tmp_path/'synthetic-unapproved-budget.json'
    config.write_text('{"synthetic_fixture_only":true}')
    config.chmod(0o600)
    before=config.read_bytes()
    state={'version':1,'observed_at':R.timestamp(),'schema_revision':manifest['source']['migration_chain'][-1],
           'unsettled_agent_runs':0,'active_jobs':0,'drained':True,'database_identity_sha256':R.database_identity(url)}
    out=tmp_path/'plan'
    R.prepare(manifest,sha,anchor,state,mode,out,env,budget_config_file=config)
    assert R.check_compose(manifest,sha,anchor,out/'compose.yml',env,mode,state)['compose_verified']
    profile=yaml.safe_load((out/'compose.yml').read_text())
    for name in ('api','worker'):
        service=profile['services'][name]
        assert service['environment']['AI_BUDGET_MODE']=='enforce'
        assert service['environment']['AI_BUDGET_CLASS']=='production'
        mount=[v for v in service['volumes'] if isinstance(v,dict) and v['target']=='/run/secrets/ai-budget.json']
        assert len(mount)==1 and mount[0]['read_only'] is True and mount[0]['source']==str(config)
        assert 'AI_BUDGET_APPROVED_MARKER' not in service['environment']
    assert config.read_bytes()==before and 'synthetic_fixture_only' not in (out/'compose.yml').read_text()
