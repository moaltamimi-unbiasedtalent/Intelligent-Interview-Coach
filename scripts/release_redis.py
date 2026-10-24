"""Optional Redis additions to an already verified immutable release profile.

No deployment, credential generation, policy activation or external publication.
"""
import copy
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import yaml


def require(ok):
    if not ok:
        raise ValueError("redis_release_configuration_refused")


def apply(profile, root, out, *, topology=None, namespace=None, password_file=None):
    if topology is None:
        require(namespace is None and password_file is None)
        return profile
    require(topology in {"internal", "managed"})
    require(isinstance(namespace, str) and re.fullmatch(r"ask4mo:rl:[A-Za-z0-9_.:-]{1,72}:", namespace))
    profile = copy.deepcopy(profile)
    for name in ("api", "worker"):
        env = profile["services"][name]["environment"]
        env.update(RATE_LIMIT_BACKEND="redis", RATE_LIMIT_SHARED_REQUIRED="true", RATE_LIMIT_NAMESPACE=namespace)
    if topology == "managed":
        require(password_file is None)
        for name in ("api", "worker"):
            profile["services"][name]["environment"]["REDIS_ALLOW_INTERNAL_PLAINTEXT"] = "false"
        return profile
    require(password_file and Path(password_file).is_absolute())
    fragment = yaml.safe_load((root / "deploy/redis-internal.yml").read_text())
    profile["services"]["redis"] = fragment["services"]["redis"]
    profile.setdefault("networks", {}).update(fragment["networks"])
    profile["secrets"] = {"redis_password": {"file": str(password_file)}}
    redis = profile["services"]["redis"]
    redis["volumes"] = [f"{Path(out).resolve() / 'redis-start.sh'}:/opt/ask4mo/redis-start.sh:ro"]
    redis["environment"] = {"RATE_LIMIT_NAMESPACE": namespace}
    for name in ("api", "worker"):
        service = profile["services"][name]
        service["networks"] = ["default", "rate-limit-store"]
        service["secrets"] = ["redis_password"]
        service["environment"].update(REDIS_URL="redis://limiter@redis:6379/0", REDIS_PASSWORD_FILE="/run/secrets/redis_password", REDIS_ALLOW_INTERNAL_PLAINTEXT="true")
        service["depends_on"]["redis"] = {"condition": "service_healthy"}
    return profile


def verify(resolved, plan, manifest, directory):
    topology = plan.get("redis_topology")
    if topology is None:
        return
    require(topology in {"internal", "managed"})
    namespace = plan["redis_namespace"]
    reference = resolved["services"]["api"]["environment"]
    for name in ("api", "worker"):
        env = resolved["services"][name]["environment"]
        require(env.get("RATE_LIMIT_BACKEND") == "redis" and env.get("RATE_LIMIT_SHARED_REQUIRED") == "true" and env.get("RATE_LIMIT_NAMESPACE") == namespace)
        require(len(env.get("RATE_LIMIT_KEY_SECRET", "")) >= 32)
        require(env["RATE_LIMIT_KEY_SECRET"] == reference["RATE_LIMIT_KEY_SECRET"] and env.get("REDIS_URL") == reference.get("REDIS_URL"))
        if topology == "managed":
            u = urlsplit(env.get("REDIS_URL", ""))
            require(u.scheme == "rediss" and u.hostname and len(unquote(u.password or "")) >= 32 and not u.query and not u.fragment)
            require(env.get("REDIS_ALLOW_INTERNAL_PLAINTEXT") == "false")
        else:
            require(env.get("REDIS_URL") == "redis://limiter@redis:6379/0" and env.get("REDIS_PASSWORD_FILE") == "/run/secrets/redis_password" and env.get("REDIS_ALLOW_INTERNAL_PLAINTEXT") == "true")
            service = resolved["services"][name]
            require(set(service["networks"]) == {"default", "rate-limit-store"})
            require(service["depends_on"]["redis"]["condition"] == "service_healthy")
            require(service.get("secrets") == [{"source": "redis_password", "target": "/run/secrets/redis_password"}])
    if topology == "internal":
        r = resolved["services"]["redis"]
        from scripts.release_images import file_hash
        require(file_hash(Path(directory) / "redis-start.sh") == manifest["source"]["deployment_files"]["deploy/scripts/redis-start.sh"])
        require(r["image"] == "redis:8.2.9-alpine@sha256:5f2e6a105b2a8cc721911d5d29aadb032c25fe55b43e829e3d03413753ff47c2")
        require(not r.get("ports") and set(r["networks"]) == {"rate-limit-store"} and resolved["networks"]["rate-limit-store"]["internal"])
        require(not resolved["networks"]["rate-limit-store"].get("external") and resolved["networks"]["rate-limit-store"]["name"] == "ask4mo-staging_rate-limit-store")
        require(r["user"] == "999:1000" and r["read_only"] and r["cap_drop"] == ["ALL"] and "no-new-privileges:true" in r["security_opt"])
        require(r["entrypoint"] == ["/bin/sh", "/opt/ask4mo/redis-start.sh"] and not r.get("command") and not r.get("privileged") and not r.get("cap_add"))
        require(r["environment"] == {"RATE_LIMIT_NAMESPACE": namespace})
        mounts = [dict(v) for v in r["volumes"]]
        require(all(v.get("bind", {}) in ({}, {"create_host_path": True}, {"create_host_path": False}) for v in mounts))
        for v in mounts:
            v.pop("bind", None)  # equivalent Compose versions normalize this optional default differently
        require(mounts == [{"type": "bind", "source": str(Path(directory).resolve() / "redis-start.sh"), "target": "/opt/ask4mo/redis-start.sh", "read_only": True}])
        require(r.get("secrets") == [{"source": "redis_password", "target": "/run/secrets/redis_password"}])
        require(set(r["tmpfs"]) == {"/tmp:rw,noexec,nosuid,size=16m,mode=1777", "/data:rw,noexec,nosuid,size=64m,uid=999,gid=1000,mode=0700"})
        require(r["healthcheck"] == {"test": ["CMD-SHELL", "REDISCLI_AUTH=$$(cat /run/secrets/redis_password) redis-cli --user limiter ping | grep -qx PONG"],
                                      "interval": "10s", "timeout": "3s", "retries": 3, "start_period": "5s"})
        require(r["restart"] == "unless-stopped")
        require(resolved["secrets"]["redis_password"]["file"] == plan["redis_password_file"])
