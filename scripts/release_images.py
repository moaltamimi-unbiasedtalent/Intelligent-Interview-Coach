#!/usr/bin/env python3
"""Local immutable release build/verify/transfer and plan-only Compose promotion.

Never deploys, publishes, migrates, downgrades, restores or reads a private .env.
Image IDs are local content addresses, NOT registry distribution digests.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # direct CLI execution resolves the reviewed scripts package
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
HASH = re.compile(r"[0-9a-f]{64}")
MINIMUM = "95fd2a3c3de5ee8af64c3f5c538b8a4824ce3ff2"


class ReleaseError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise ReleaseError(code)


def decode_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=unique)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected.split()), "manifest_fields_invalid")


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parsed_time(value):
    require(isinstance(value, str), "timestamp_invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReleaseError("timestamp_invalid") from exc


def run(args, *, cwd=None, input=None, timeout=300):
    result = subprocess.run(args, cwd=cwd, input=input, capture_output=True, timeout=timeout)
    require(result.returncode == 0, "command_failed:" + args[0])
    return result.stdout


@contextmanager
def committed_source(sha, repo=ROOT):
    require(isinstance(sha, str) and SHA.fullmatch(sha), "application_sha_invalid")
    require(run(["git", "rev-parse", sha + "^{commit}"], cwd=repo).decode().strip() == sha, "application_sha_invalid")
    run(["git", "merge-base", "--is-ancestor", MINIMUM, sha], cwd=repo)
    archive = run(["git", "archive", "--format=tar", sha], cwd=repo)
    with tempfile.TemporaryDirectory(prefix="ask4mo-release-source-") as directory:
        root = Path(directory).resolve()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                require(not member.issym() and not member.islnk() and (member.isdir() or member.isfile()), "unsafe_source_member")
                require((root / member.name).resolve().is_relative_to(root), "unsafe_source_path")
            tar.extractall(root, filter="data")
        yield root


def migration_chain(root):
    import ast
    revisions = {}
    for path in sorted((root / "migrations/versions").glob("0*.py")):
        values = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("revision", "down_revision"):
                        values[target.id] = ast.literal_eval(node.value)
        require(set(values) == {"revision", "down_revision"} and isinstance(values["revision"], str) and
                (values["down_revision"] is None or isinstance(values["down_revision"], str)), "migration_graph_invalid")
        require(values["revision"] not in revisions, "migration_graph_invalid")
        revisions[values["revision"]] = values["down_revision"]
    heads = set(revisions) - set(revisions.values())
    require(len(heads) == 1, "migration_head_not_single")
    chain, item = [], next(iter(heads))
    while item is not None:
        require(item in revisions and item not in chain, "migration_graph_invalid")
        chain.append(item)
        item = revisions[item]
    require(len(chain) == len(revisions), "migration_graph_invalid")
    return list(reversed(chain))


def hashes(root, names):
    return {name: file_hash(root / name) for name in sorted(names)}


def tree_names(root, directory):
    return [p.relative_to(root).as_posix() for p in (root / directory).rglob("*") if p.is_file()]


def source_record(root, sha):
    import ast
    policy = decode_json((root / "deploy/release-policy.json").read_text())
    keys(policy, "version minimum_source_sha compatible_schema_revisions")
    chain = migration_chain(root)
    require(type(policy["version"]) is int and policy == {"version": 1, "minimum_source_sha": MINIMUM, "compatible_schema_revisions": [chain[-1]]}, "schema_policy_requires_review")
    flags = {}
    for node in ast.parse((root / "src/billing/policy.py").read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            flags.update({n.id: node.value.value for n in node.targets if isinstance(n, ast.Name)})
    require(all(flags.get(name) is False for name in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED",
            "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")), "billing_not_disabled")
    api = ["README.md", "requirements.txt", "pyproject.toml", "alembic.ini"]
    for directory in ("src", "migrations", "prompts", "scripts"):
        api += tree_names(root, directory)
    api_files = hashes(root, api)
    api_files["scripts/migrate.sh"] = file_hash(root / "deploy/scripts/migrate.sh")
    api_files["release-policy.json"] = file_hash(root / "deploy/release-policy.json")
    activation = "docs/production/execution/language_readiness.json"
    api_files[activation] = file_hash(root / activation)
    # Everything fed to the frontend build is committed, even though only the
    # compiled app, public files and dependency files ship in its runtime stage.
    web_inputs = hashes(root, tree_names(root, "frontend"))
    web_files = {name.removeprefix("frontend/"): value for name, value in web_inputs.items()
                 if name in ("frontend/package.json", "frontend/package-lock.json", "frontend/next.config.mjs") or name.startswith("frontend/public/")}
    governor = root / "src/llm/budget/governor.py"
    policy_version = None
    if governor.exists():
        for node in ast.parse(governor.read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "HOSTED_POLICY_VERSION" for t in node.targets):
                policy_version = ast.literal_eval(node.value)
    return {"budget_policy_version": policy_version, "application_sha": sha, "migration_chain": chain, "compatible_schema_revisions": policy["compatible_schema_revisions"],
            "api_files": api_files, "web_files": web_files, "web_input_sha256": digest(canonical(web_inputs)),
            "dockerfiles": hashes(root, ["deploy/Dockerfile.api", "deploy/Dockerfile.web", ".dockerignore"]),
            "prompt_files": hashes(root, tree_names(root, "prompts")), "language_activation_sha256": api_files[activation],
            "deployment_files": hashes(root, ["deploy/docker-compose.staging.yml", "deploy/Caddyfile", "deploy/release-policy.json"] + [p for p in ("deploy/redis-internal.yml", "deploy/scripts/redis-start.sh") if (root / p).is_file()]),
            "billing_disabled": True}


API_PROBE = r'''
import hashlib, importlib.metadata, json, os, pathlib, platform, subprocess, sys
paths = json.load(sys.stdin)
print(json.dumps({"files": {p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths},
 "dependencies": sorted([{ "name": d.metadata['Name'], "version": d.version} for d in importlib.metadata.distributions()], key=lambda x:(x['name'],x['version'])),
 "os_dependencies": [dict(zip(('name','version'), line.split('\t'))) for line in subprocess.check_output(['dpkg-query','-W','-f=${Package}\t${Version}\n'],text=True).splitlines()],
 "runtime": platform.python_version(), "uid": os.getuid()}))
'''
WEB_PROBE = r'''
const fs=require('fs'), crypto=require('crypto'), cp=require('child_process');
let input='';process.stdin.on('data',s=>input+=s);process.stdin.on('end',()=>{
 const paths=JSON.parse(input), hash=b=>crypto.createHash('sha256').update(b).digest('hex');
 const pkg=JSON.parse(fs.readFileSync('package.json'));
 const dependencies=Object.keys(pkg.dependencies||{}).sort().map(name=>({name,version:JSON.parse(fs.readFileSync('node_modules/'+name+'/package.json')).version}));
 const buildId=fs.readFileSync('.next/BUILD_ID','utf8').trim();if(!buildId)throw Error('missing build');
 const os_dependencies=cp.execFileSync('dpkg-query',['-W','-f=${Package}\t${Version}\n'],{encoding:'utf8'}).trim().split('\n').map(line=>{const [name,version]=line.split('\t');return {name,version}});
 console.log(JSON.stringify({files:Object.fromEntries(paths.map(p=>[p,hash(fs.readFileSync(p))])),dependencies,os_dependencies,runtime:process.versions.node,uid:process.getuid(),build_id:buildId}));
});
'''


def inspect_image(image_id, role, source, created, api_url):
    require(isinstance(image_id, str) and DIGEST.fullmatch(image_id), "image_digest_invalid")
    info = json.loads(run(["docker", "image", "inspect", image_id]))[0]
    require(info["Id"] == image_id, "image_digest_mismatch")
    config = info["Config"]
    labels = config.get("Labels") or {}
    expected = {"org.opencontainers.image.revision": source["application_sha"], "org.opencontainers.image.created": created,
                "io.ask4mo.source.sha256": digest(canonical(source)), "io.ask4mo.role": role}
    require(all(labels.get(k) == v for k, v in expected.items()), "image_metadata_mismatch")
    require(config.get("User") == ("appuser" if role == "application" else "node") and
            config.get("Entrypoint") == (None if role == "application" else ["docker-entrypoint.sh"]), "image_security_mismatch")
    require(config.get("WorkingDir") == ("/app" if role == "application" else "/app/frontend"), "image_workdir_mismatch")
    require(config.get("Cmd") == (["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"] if role == "application" else
                                 ["npm", "run", "start", "--", "-p", "3000"]), "image_command_mismatch")
    env = dict(v.split("=", 1) for v in config.get("Env", []) if "=" in v)
    require(env.get("APP_GIT_SHA") == source["application_sha"] and env.get("APP_BUILD_TIME") == created, "image_metadata_mismatch")
    require(not any(env.get(k) for k in ("DATABASE_URL", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "SECRET_STORE_MASTER_KEY", "BREVO_API_KEY")), "image_contains_runtime_secret")
    if role == "web":
        require(env.get("NEXT_PUBLIC_API_BASE_URL") == api_url, "frontend_api_url_mismatch")
    paths = source["api_files" if role == "application" else "web_files"]
    args = ["python", "-c", API_PROBE] if role == "application" else ["node", "-e", WEB_PROBE]
    result = json.loads(run(["docker", "run", "--rm", "-i", "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", image_id, *args], input=canonical(list(paths))))
    require(result.pop("files") == paths, "image_source_file_mismatch")
    require(result["uid"] == (10001 if role == "application" else 1000), "image_security_mismatch")
    require(info["Os"] == "linux", "image_platform_invalid")
    created_time = datetime.fromisoformat(info["Created"].replace("Z", "+00:00"))
    require(created_time.utcoffset() is not None, "timestamp_invalid")
    normalized_created = created_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"image_id": image_id, "registry_digest": None, "platform": info["Os"] + "/" + info["Architecture"],
            "docker_created_at": normalized_created, "contents": result}


def public_url(value):
    require(isinstance(value, str), "public_api_url_invalid")
    require(value == value.strip() and "?" not in value and "#" not in value and not any(c.isspace() or ord(c) < 32 for c in value), "public_api_url_invalid")
    url = urlsplit(value)
    try:
        port = url.port
    except ValueError as exc:
        raise ReleaseError("public_api_url_invalid") from exc
    require(port is None or 1 <= port <= 65535, "public_api_url_invalid")
    require(url.hostname == "::1" or bool(url.hostname and re.fullmatch(r"[A-Za-z0-9.-]+", url.hostname)), "public_api_url_invalid")
    require(not url.username and not url.password and not url.query and not url.fragment and url.path == "/api/v1" and
            (url.scheme == "https" and url.hostname or url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost", "::1")), "public_api_url_invalid")


def validate_manifest(manifest, expected_sha, anchor, *, repo=ROOT, verify_images=True):
    require(HASH.fullmatch(anchor or "") and digest(canonical(manifest)) == anchor, "manifest_anchor_mismatch")
    keys(manifest, "version kind application_sha build_started_at public_api_base_url source images")
    require(type(manifest["version"]) is int and manifest["version"] == 1 and manifest["kind"] == "local-docker-image-id", "manifest_version_invalid")
    require(SHA.fullmatch(expected_sha or "") and manifest["application_sha"] == expected_sha, "application_sha_mismatch")
    parsed_time(manifest["build_started_at"])
    public_url(manifest["public_api_base_url"])
    with committed_source(expected_sha, repo) as root:
        source = source_record(root, expected_sha)
    require(manifest["source"] == source, "source_record_mismatch")
    keys(manifest["images"], "application web")
    for role, image in manifest["images"].items():
        keys(image, "image_id registry_digest platform docker_created_at contents")
        require(isinstance(image["image_id"], str) and DIGEST.fullmatch(image["image_id"]), "image_digest_invalid")
        require(image["registry_digest"] is None, "registry_publication_not_supported")
        require(isinstance(image["platform"], str) and re.fullmatch(r"linux/[a-z0-9_]+", image["platform"]), "image_platform_invalid")
        require(isinstance(image["docker_created_at"], str), "timestamp_invalid")
        try:
            image_time = datetime.fromisoformat(image["docker_created_at"].replace("Z", "+00:00"))
            require(image_time.utcoffset() is not None and image_time.utcoffset().total_seconds() == 0, "timestamp_invalid")
        except ValueError as exc:
            raise ReleaseError("timestamp_invalid") from exc
        contents = image["contents"]
        keys(contents, "dependencies os_dependencies runtime uid" + (" build_id" if role == "web" else ""))
        require(type(contents["uid"]) is int and contents["uid"] == (10001 if role == "application" else 1000), "image_security_mismatch")
        require(isinstance(contents["runtime"], str) and re.fullmatch(r"[0-9.]+", contents["runtime"]), "dependency_metadata_invalid")
        if role == "web":
            require(isinstance(contents["build_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", contents["build_id"]), "frontend_build_id_invalid")
        for field in ("dependencies", "os_dependencies"):
            require(isinstance(contents[field], list) and len(contents[field]) > 0, "dependency_metadata_invalid")
            for dependency in contents[field]:
                keys(dependency, "name version")
                require(isinstance(dependency["name"], str) and re.fullmatch(r"[A-Za-z0-9@][A-Za-z0-9_.@/+-]*", dependency["name"]) and
                        isinstance(dependency["version"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+!:~_-]*", dependency["version"]), "dependency_metadata_invalid")
        if verify_images:
            actual = inspect_image(image["image_id"], role, source, manifest["build_started_at"], manifest["public_api_base_url"])
            require(actual == image, "image_record_mismatch")
    require(manifest["images"]["application"]["platform"] == manifest["images"]["web"]["platform"], "image_platform_mismatch")
    if verify_images:
        native = run(["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"]).decode().strip()
        require(native == manifest["images"]["application"]["platform"], "image_platform_not_native")
    require(manifest["images"]["application"]["image_id"] != manifest["images"]["web"]["image_id"], "image_roles_mismatch")
    return manifest


def new_directory(path):
    path = Path(path).resolve()
    require(not path.exists(), "output_exists")
    path.mkdir(parents=True)
    return path


def write_json(path, value):
    with Path(path).open("x") as f:
        f.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build_release(sha, api_url, out, *, repo=ROOT):
    public_url(api_url)
    out = new_directory(out)
    created, images = timestamp(), {}
    with committed_source(sha, repo) as root:
        source = source_record(root, sha)
        stamp = digest(canonical(source))
        for role, filename in (("application", "api"), ("web", "web")):
            tag = f"ask4mo-local-{filename}:{sha[:12]}-{uuid.uuid4().hex[:10]}"
            args = ["docker", "build", "--provenance=false", "-f", f"deploy/Dockerfile.{filename}", "-t", tag,
                    "--build-arg", f"APP_GIT_SHA={sha}", "--build-arg", f"APP_BUILD_TIME={created}",
                    "--build-arg", f"APP_SOURCE_SHA256={stamp}"]
            if role == "web":
                args += ["--build-arg", f"NEXT_PUBLIC_API_BASE_URL={api_url}"]
            with (out / f"{filename}-build.log").open("x") as log:
                completed = subprocess.run([*args, "."], cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
            require(completed.returncode == 0, "image_build_failed:" + role)
            image_id = json.loads(run(["docker", "image", "inspect", tag]))[0]["Id"]
            images[role] = inspect_image(image_id, role, source, created, api_url)
    manifest = {"version": 1, "kind": "local-docker-image-id", "application_sha": sha, "build_started_at": created,
                "public_api_base_url": api_url, "source": source, "images": images}
    anchor = digest(canonical(manifest))
    validate_manifest(manifest, sha, anchor, repo=repo)
    write_json(out / "release.json", manifest)
    (out / "release.sha256").write_text(anchor + "\n")
    return {"application_sha": sha, "manifest_sha256": anchor, "images": {k: v["image_id"] for k, v in images.items()}}


def database_identity(url):
    """Non-secret logical target binding; credentials and URL queries are excluded."""
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    identity = {"backend": backend, "database": parsed.database or ""}
    if backend == "sqlite":
        identity["database"] = str(Path(parsed.database or "").resolve())
    else:
        identity.update(host=parsed.host or "", port=parsed.port or 5432,
                        namespace_options={key: parsed.query[key] for key in ("options", "search_path", "currentSchema") if key in parsed.query})
    return digest(canonical(identity))


def check_state(state, manifest, mode, *, now=None):
    keys(state, "version observed_at schema_revision unsettled_agent_runs active_jobs drained database_identity_sha256")
    require(isinstance(state["database_identity_sha256"], str) and HASH.fullmatch(state["database_identity_sha256"]), "database_identity_invalid")
    require(type(state["version"]) is int and state["version"] == 1, "state_version_invalid")
    require(mode in ("promote", "rollback"), "promotion_mode_invalid")
    age = ((now or datetime.now(timezone.utc)) - parsed_time(state["observed_at"])).total_seconds()
    require(0 <= age <= 300, "state_observation_stale")
    require(state["drained"] is True, "drain_attestation_required")
    require(type(state["unsettled_agent_runs"]) is int and type(state["active_jobs"]) is int and
            state["unsettled_agent_runs"] == state["active_jobs"] == 0, "active_or_unsettled_work")
    require(manifest["source"].get("budget_policy_version") == 2, "budget_policy_incapable_image")
    chain = manifest["source"]["migration_chain"]
    if mode == "rollback":
        require(state["schema_revision"] in manifest["source"]["compatible_schema_revisions"], "rollback_schema_incompatible")
    else:
        require(state["schema_revision"] == "base" or state["schema_revision"] in chain, "promotion_schema_incompatible")


def profile_for(manifest, base, state, mode, env_file, caddyfile):
    import copy
    require(mode in ("promote", "rollback"), "promotion_mode_invalid")
    require(Path(env_file).is_absolute() and Path(caddyfile).is_absolute(), "runtime_paths_must_be_absolute")
    check_state(state, manifest, mode)
    require(manifest["source"].get("budget_policy_version") == 2, "budget_policy_incapable_image")
    profile = copy.deepcopy(base)
    services = profile["services"]
    for name in ("api", "worker", "migrate", "web"):
        service = services[name]
        service.pop("build", None)
        service["image"] = manifest["images"]["web" if name == "web" else "application"]["image_id"]
        service["pull_policy"] = "never"
        service["labels"] = {"io.ask4mo.release.sha": manifest["application_sha"], "io.ask4mo.manifest.sha256": digest(canonical(manifest))}
        service.setdefault("environment", {}).update(APP_GIT_SHA=manifest["application_sha"], APP_BUILD_TIME=manifest["build_started_at"])
        if name != "web":
            service["environment"]["API_ENV"] = "staging"
            if name in ("api", "worker"):
                service["environment"].update(AI_BUDGET_MODE="enforce", AI_BUDGET_CLASS="production")
        else:
            service["environment"]["NODE_ENV"] = "production"
    endpoint = urlsplit(manifest["public_api_base_url"])
    require(endpoint.scheme == "https" and endpoint.port in (None, 443), "staging_proxy_requires_https")
    services["caddy"]["environment"]["API_DOMAIN"] = endpoint.hostname
    services["web"]["environment"]["NEXT_PUBLIC_API_BASE_URL"] = manifest["public_api_base_url"]
    services["web"]["environment"]["NEXT_TELEMETRY_DISABLED"] = "1"
    for service in services.values():
        if "env_file" in service:
            service["env_file"] = [str(env_file)]
    services["caddy"]["volumes"][0] = f"{caddyfile}:/etc/caddy/Caddyfile:ro"
    if mode == "rollback":
        del services["migrate"]  # an application rollback never runs any Alembic command
        for name in ("api", "worker"):
            del services[name]["depends_on"]["migrate"]
    else:
        require(services["migrate"]["command"] == ["bash", "scripts/migrate.sh"] and services["migrate"]["restart"] == "no", "migration_topology_mismatch")
        for name in ("api", "worker"):
            require(services[name]["depends_on"]["migrate"] == {"condition": "service_completed_successfully"}, "migration_dependency_mismatch")
    return profile


def prepare(manifest, expected_sha, anchor, state, mode, out, env_file, *, repo=ROOT, redis_topology=None, redis_namespace=None, redis_password_file=None, budget_config_file=None):
    validate_manifest(manifest, expected_sha, anchor, repo=repo)
    if redis_topology:
        require(any(d["name"].lower() == "redis" and d["version"] == "8.1.0" for d in manifest["images"]["application"]["contents"]["dependencies"]), "release_redis_client_unavailable")
    with committed_source(expected_sha, repo) as root:
        base = yaml.safe_load((root / "deploy/docker-compose.staging.yml").read_text())
        caddy = (root / "deploy/Caddyfile").read_bytes()
        profile = profile_for(manifest, base, state, mode, env_file, Path(out).resolve() / "Caddyfile")
        if budget_config_file:
            budget_path = Path(budget_config_file)
            require(budget_path.is_absolute() and budget_path.is_file() and not (budget_path.stat().st_mode & 0o007), "budget_runtime_file_invalid")
            for name in ("api", "worker"):
                profile["services"][name]["environment"]["AI_BUDGET_CONFIG_PATH"] = "/run/secrets/ai-budget.json"
                profile["services"][name].setdefault("volumes", []).append({"type": "bind", "source": str(budget_path), "target": "/run/secrets/ai-budget.json", "read_only": True, "bind": {"create_host_path": False}})
        else:
            for name in ("api", "worker"):
                profile["services"][name]["environment"]["AI_BUDGET_CONFIG_PATH"] = ""
        from scripts.release_redis import apply
        profile = apply(profile, root, out, topology=redis_topology, namespace=redis_namespace, password_file=redis_password_file)
        redis_script = (root / "deploy/scripts/redis-start.sh").read_bytes() if redis_topology == "internal" else None
    out = new_directory(out)
    (out / "compose.yml").write_text(yaml.safe_dump(profile, sort_keys=False))
    (out / "Caddyfile").write_bytes(caddy)
    if redis_script is not None:
        (out / "redis-start.sh").write_bytes(redis_script)
    write_json(out / "plan.json", {"mode": mode, "application_sha": expected_sha, "manifest_sha256": anchor,
               "state_sha256": digest(canonical(state)), "state_observed_at": state["observed_at"],
               "database_identity_sha256": state["database_identity_sha256"],
               "compose_sha256": file_hash(out / "compose.yml"), "caddy_sha256": file_hash(out / "Caddyfile"),
               "drain_evidence": "operator attestation; process drain not verified by this tool", "executed": False,
               "budget_config_file": str(budget_config_file) if budget_config_file else None,
               "redis_topology": redis_topology, "redis_namespace": redis_namespace, "redis_password_file": str(redis_password_file) if redis_password_file else None,
               "migrations": "one-shot upgrade only" if mode == "promote" else "none; application images only"})
    return {"mode": mode, "manifest_sha256": anchor, "executed": False}


def check_compose(manifest, expected_sha, anchor, profile, env_file, mode, state, *, repo=ROOT):
    validate_manifest(manifest, expected_sha, anchor, repo=repo)
    check_state(state, manifest, mode)
    plan = decode_json((Path(profile).parent / "plan.json").read_text())
    require(plan["manifest_sha256"] == anchor and plan["state_sha256"] == digest(canonical(state)), "plan_observation_mismatch")
    require(plan["compose_sha256"] == file_hash(profile), "prepared_profile_modified")
    copied_caddy = Path(profile).parent.resolve() / "Caddyfile"
    require(file_hash(copied_caddy) == plan["caddy_sha256"] == manifest["source"]["deployment_files"]["deploy/Caddyfile"], "proxy_config_modified")
    require(mode in ("promote", "rollback"), "promotion_mode_invalid")
    # stdout contains resolved secrets: capture privately, inspect only bounded
    # identity/topology fields, and never print or persist the resolved document.
    resolved = json.loads(run(["docker", "compose", "--env-file", str(env_file), "-f", str(profile), "config", "--format", "json"]))
    services = resolved["services"]
    proxy_mount = services["caddy"]["volumes"][0]
    require(proxy_mount["type"] == "bind" and proxy_mount["target"] == "/etc/caddy/Caddyfile" and proxy_mount.get("read_only") is True and
            Path(proxy_mount["source"]).resolve() == copied_caddy, "proxy_config_mismatch")
    expected_services = {"api", "worker", "web", "db", "clamav", "caddy"} | ({"migrate"} if mode == "promote" else set())
    if plan.get("redis_topology") == "internal":
        expected_services.add("redis")
    require(set(services) == expected_services, "resolved_service_mismatch")
    from scripts.release_redis import verify
    verify(resolved, plan, manifest, Path(profile).parent)
    require(resolved["name"] == "ask4mo-staging", "resolved_project_mismatch")
    app_names = ("api", "worker", "migrate", "web") if mode == "promote" else ("api", "worker", "web")
    for name in app_names:
        service = services[name]
        require("build" not in service and service["pull_policy"] == "never", "resolved_build_or_pull")
        require(not service.get("entrypoint") and not service.get("user") and not service.get("privileged") and not service.get("cap_add"), "resolved_security_override")
        if name == "worker":
            require(service.get("command") == ["python", "-m", "src.jobs.worker"], "resolved_worker_command_mismatch")
        elif name in ("api", "web"):
            require(not service.get("command"), "resolved_application_command_override")
        volumes = service.get("volumes", [])
        if name in ("api", "worker"):
            require(service["environment"].get("AI_BUDGET_MODE") == "enforce" and service["environment"].get("AI_BUDGET_CLASS") == "production", "budget_runtime_policy_mismatch")
            bindings = [v for v in volumes if v["target"] == "/run/secrets/ai-budget.json"]
            configured = plan.get("budget_config_file")
            require(service["environment"].get("AI_BUDGET_CONFIG_PATH", "") == ("/run/secrets/ai-budget.json" if configured else ""), "budget_runtime_path_mismatch")
            require(len(bindings) == (1 if configured else 0), "budget_runtime_mount_mismatch")
            if configured:
                require(bindings[0]["type"] == "bind" and bindings[0].get("read_only") is True and bindings[0]["source"] == configured, "budget_runtime_mount_mismatch")
            volumes = [v for v in volumes if v not in bindings]
        expected_mounts = {("/data/documents", "documents"), ("/data/knowledge", "knowledge-data")} if name in ("api", "worker") else set()
        require(all(v["type"] == "volume" for v in volumes) and {(v["target"], v["source"]) for v in volumes} == expected_mounts, "resolved_private_volume_mismatch")
        require(service["image"] == manifest["images"]["web" if name == "web" else "application"]["image_id"], "resolved_image_mismatch")
        for volume in volumes:
            require(resolved["volumes"][volume["source"]]["name"] == "ask4mo-staging_" + volume["source"], "resolved_private_volume_mismatch")
        if name != "web":
            require(service["environment"].get("DATABASE_URL") and database_identity(service["environment"]["DATABASE_URL"]) == state["database_identity_sha256"], "runtime_database_identity_mismatch")
        require(service["labels"]["io.ask4mo.manifest.sha256"] == anchor and service["environment"]["APP_GIT_SHA"] == expected_sha,
                "resolved_release_mismatch")
        require(service["environment"].get("NODE_ENV" if name == "web" else "API_ENV") == ("production" if name == "web" else "staging"), "resolved_runtime_mismatch")
    require(services["web"]["environment"]["NEXT_PUBLIC_API_BASE_URL"] == manifest["public_api_base_url"], "frontend_api_url_mismatch")
    require(services["caddy"]["environment"]["API_DOMAIN"] == urlsplit(manifest["public_api_base_url"]).hostname, "proxy_api_domain_mismatch")
    require(services["web"]["environment"]["NEXT_TELEMETRY_DISABLED"] == "1", "frontend_telemetry_not_disabled")
    if mode == "promote":
        require(services["migrate"]["command"] == ["bash", "scripts/migrate.sh"] and services["migrate"]["restart"] == "no", "migration_topology_mismatch")
        for name in ("api", "worker"):
            require(services[name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully", "migration_dependency_mismatch")
    else:
        require(all("migrate" not in services[name].get("depends_on", {}) for name in ("api", "worker")), "rollback_migration_forbidden")
    return {"manifest_sha256": anchor, "compose_verified": True, "executed": False}


def export_images(manifest, expected_sha, anchor, out, *, repo=ROOT):
    validate_manifest(manifest, expected_sha, anchor, repo=repo)
    out = new_directory(out)
    archive = out / "images.tar.gz"
    process = subprocess.Popen(["docker", "image", "save", *[v["image_id"] for v in manifest["images"].values()]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with archive.open("xb") as f, gzip.GzipFile(fileobj=f, mode="wb", compresslevel=1, mtime=0) as compressed:
        shutil.copyfileobj(process.stdout, compressed)
    process.stdout.close()
    process.stderr.read()  # do not publish daemon diagnostics / host details
    require(process.wait(timeout=300) == 0, "image_export_failed")
    transfer = {"version": 1, "manifest_sha256": anchor, "archive_sha256": file_hash(archive)}
    write_json(out / "transfer.json", transfer)
    return transfer


def import_images(manifest, expected_sha, anchor, archive, archive_anchor, *, repo=ROOT):
    validate_manifest(manifest, expected_sha, anchor, repo=repo, verify_images=False)
    require(HASH.fullmatch(archive_anchor or "") and file_hash(archive) == archive_anchor, "archive_digest_mismatch")
    run(["docker", "image", "load", "--input", str(archive)], timeout=600)
    validate_manifest(manifest, expected_sha, anchor, repo=repo)
    return {"manifest_sha256": anchor, "loaded_and_verified": True}


def observe_disposable(url, *, drained=False):
    """Read-only counts, only from explicit temporary SQLite or loopback test PG.

    No .env loading and no DATABASE_URL fallback. This is NOT a hosted observer.
    """
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        path = Path(parsed.database or "").resolve()
        require(path.is_relative_to(Path(tempfile.gettempdir()).resolve()) and path.is_file(), "disposable_database_required")
    else:
        require(parsed.get_backend_name() == "postgresql" and parsed.host in ("127.0.0.1", "localhost", "::1") and
                (parsed.database or "").startswith("p5b_"), "disposable_database_required")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("PRAGMA query_only=ON" if parsed.get_backend_name() == "sqlite" else "SET TRANSACTION READ ONLY"))
            tables = set(inspect(connection).get_table_names())
            revisions = list(connection.scalars(text("SELECT version_num FROM alembic_version"))) if "alembic_version" in tables else []
            require(len(revisions) <= 1, "database_heads_not_single")
            require(bool(revisions) or tables <= {"alembic_version"}, "unversioned_nonempty_database")
            if revisions and revisions[0] == migration_chain(ROOT)[-1]:
                require("agent_run_controls" in tables, "current_schema_missing_run_controls")
            unsettled = connection.scalar(text("SELECT count(*) FROM agent_run_controls WHERE settled = false")) if "agent_run_controls" in tables else 0
            jobs = connection.scalar(text("SELECT count(*) FROM jobs WHERE status IN ('queued','running')")) if "jobs" in tables else 0
        return {"version": 1, "observed_at": timestamp(), "schema_revision": revisions[0] if revisions else "base",
                "unsettled_agent_runs": unsettled, "active_jobs": jobs, "drained": drained, "database_identity_sha256": database_identity(url)}
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--sha", required=True)
    build.add_argument("--api-base-url", required=True)
    build.add_argument("--out", required=True)
    for name in ("verify", "prepare", "export", "import", "check-compose"):
        child = sub.add_parser(name)
        child.add_argument("--manifest", required=True)
        child.add_argument("--expected-sha", required=True)
        child.add_argument("--manifest-sha256", required=True)
        if name in ("prepare", "export"):
            child.add_argument("--out", required=True)
        if name == "prepare":
            child.add_argument("--budget-config-file")
            child.add_argument("--redis-topology", choices=("internal", "managed"))
            child.add_argument("--redis-namespace")
            child.add_argument("--redis-password-file")
            child.add_argument("--state", required=True)
            child.add_argument("--mode", choices=("promote", "rollback"), required=True)
            child.add_argument("--env-file", required=True)
        if name == "check-compose":
            child.add_argument("--state", required=True)
            child.add_argument("--profile", required=True)
            child.add_argument("--env-file", required=True)
            child.add_argument("--mode", choices=("promote", "rollback"), required=True)
        if name == "import":
            child.add_argument("--archive", required=True)
            child.add_argument("--archive-sha256", required=True)
    observe = sub.add_parser("observe-disposable")
    observe.add_argument("--out", required=True)
    observe.add_argument("--attest-drained", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_release(args.sha, args.api_base_url, args.out)
        elif args.command == "observe-disposable":
            url = os.environ.get("RELEASE_TEST_DATABASE_URL")
            require(url, "explicit_disposable_database_required")
            result = observe_disposable(url, drained=args.attest_drained)
            write_json(args.out, result)
        else:
            manifest = decode_json(Path(args.manifest).read_text())
            common = (manifest, args.expected_sha, args.manifest_sha256)
            if args.command == "prepare":
                result = prepare(*common, decode_json(Path(args.state).read_text()), args.mode, args.out, args.env_file, redis_topology=args.redis_topology, redis_namespace=args.redis_namespace, redis_password_file=args.redis_password_file, budget_config_file=args.budget_config_file)
            elif args.command == "check-compose":
                result = check_compose(*common, args.profile, args.env_file, args.mode, decode_json(Path(args.state).read_text()))
            elif args.command == "export":
                result = export_images(*common, args.out)
            elif args.command == "import":
                result = import_images(*common, args.archive, args.archive_sha256)
            else:
                validate_manifest(*common)
                result = {"manifest_sha256": args.manifest_sha256, "verified": True}
        print(json.dumps(result, sort_keys=True))
        return 0
    except ReleaseError as exc:
        print(json.dumps({"error": str(exc)}))  # fixed code only, never raw tool output
        return 1
    except Exception:  # CLI boundary: refuse with nonzero status, never echo raw driver/config errors.
        # Never echo a private URL, env, raw Docker config or database exception.
        print(json.dumps({"error": "release_operation_refused"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
