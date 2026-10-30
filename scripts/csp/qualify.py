#!/usr/bin/env python3
"""Opt-in Linux-only built-image CSP regression. No registry, live provider or private env.

Builds the pinned pre-fix frontend from committed main and compares it with the
verified candidate release. Only a synthetic PostgreSQL/auth fixture is seeded.
"""

from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import release_images as R  # noqa: E402

BASE = "992682c3fa9c891f5710c993e7d595f363b8c811"
LABEL = "io.ask4mo.csp.disposable"
PG = "postgres:16@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97"
CADDY = (
    "caddy:2@sha256:04913b1da43339a40ad1ea87827d70a576ac5aa6cf674c6e24fdca675887533a"
)


def safe_runner_value(value):
    import re

    return value if re.fullmatch(r"(?:ubuntu\d{2}|\d{8}\.\d{1,6}\.\d{1,3})", value) else "unavailable"


def require(ok, code):
    if not ok:
        raise ValueError(code)


def expected_database_head(manifest):
    """Select the single reviewed head from an already validated release manifest."""
    source = manifest.get("source") if isinstance(manifest, dict) else None
    require(isinstance(source, dict), "invalid_manifest_schema")
    chain = source.get("migration_chain")
    compatible = source.get("compatible_schema_revisions")
    require(isinstance(chain, list) and bool(chain) and all(isinstance(x, str) and x for x in chain), "invalid_manifest_schema")
    require(compatible == [chain[-1]], "invalid_manifest_schema")
    return chain[-1]


def require_database_head(observed, expected):
    require(isinstance(expected, str) and bool(expected), "invalid_manifest_schema")
    require(observed == [expected], "unexpected_database_head")


def run(args, *, timeout=180, env=None, check=True):
    p = subprocess.run(
        [str(a) for a in args], capture_output=True, timeout=timeout, env=env
    )
    require(not check or p.returncode == 0, "csp_command_failed")
    return p


def local_caddy(source):
    require(source.count("email {$ACME_EMAIL}") == 1, "unexpected_edge_config")
    # Only certificate/HTTP redirect behaviour changes for reserved offline domains.
    # All CSP, security and trusted-proxy directives remain byte-for-byte intact.
    lines = []
    for line in source.splitlines():
        if line.strip() == "email {$ACME_EMAIL}":
            line = line.replace("email {$ACME_EMAIL}", "auto_https disable_redirects")
        if line.strip() == "encode gzip zstd":
            lines.append(line[: len(line) - len(line.lstrip())] + "tls internal")
        lines.append(line)
    return "\n".join(lines) + "\n"


class Check:
    def __init__(self, args):
        self.args = args
        self.token = uuid.uuid4().hex[:16]
        self.project = "ask4mo-csp-" + self.token
        self.out = Path(args.out).resolve()
        self.created = False
        self.owns_output = False
        self.summary = {
            "source_sha": args.sha,
            "baseline_sha": BASE,
            "result": "FAIL",
            "production_or_language_approval": False,
            "diagnostic_environment": {
                "python": ".".join(str(v) for v in sys.version_info[:3]),
                # Project only known runner metadata; never serialize os.environ.
                "runner_image": safe_runner_value(os.environ.get("ImageOS", "")),
                "runner_image_version": safe_runner_value(os.environ.get("ImageVersion", "")),
            },
        }

    def compose(self, *args, **kw):
        return run(
            [
                "docker",
                "compose",
                "--env-file",
                self.out / "private/runtime.env",
                "-p",
                self.project,
                "-f",
                self.out / "private/compose.yml",
                *args,
            ],
            **kw,
        )

    def prepare(self):
        require(sys.platform.startswith("linux"), "linux_local_docker_host_required")
        require(not self.out.exists(), "new_output_directory_required")
        self.summary["phase"] = "verify_candidate_manifest"
        m = R.decode_json(Path(self.args.manifest).read_text())
        R.validate_manifest(m, self.args.sha, self.args.anchor)
        self.expected_schema = expected_database_head(m)
        require(
            m["public_api_base_url"] == "https://api.staging.example.com/api/v1",
            "reserved_api_origin_required",
        )
        self.out.mkdir(mode=0o700)
        self.owns_output = True
        private = self.out / "private"
        private.mkdir(mode=0o700)
        capacity = run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "python",
                m["images"]["application"]["image_id"],
                "-c",
                "import shutil; print(shutil.disk_usage('/app').free)",
            ]
        ).stdout
        require(int(capacity) >= 8 * 1024**3, "insufficient_docker_capacity")
        self.summary["docker_available_bytes_before"] = int(capacity)
        self.summary["images"] = {k: v["image_id"] for k, v in m["images"].items()}
        self.summary["manifest_sha256"] = self.args.anchor
        self.summary["phase"] = "build_original_frontend"
        with R.committed_source(BASE) as source:
            source_record = R.source_record(source, BASE)
            source_hash = R.digest(R.canonical(source_record))
            built_at = R.timestamp()
            tag = "ask4mo-csp-baseline:" + self.token
            with (private / "baseline-build.log").open("x") as log:
                p = subprocess.run(
                    [
                        "docker",
                        "build",
                        "--provenance=false",
                        "-f",
                        "deploy/Dockerfile.web",
                        "-t",
                        tag,
                        "--build-arg",
                        "NEXT_PUBLIC_API_BASE_URL=https://api.staging.example.com/api/v1",
                        "--build-arg",
                        "APP_GIT_SHA=" + BASE,
                        "--build-arg",
                        "APP_BUILD_TIME=" + built_at,
                        "--build-arg",
                        "APP_SOURCE_SHA256=" + source_hash,
                        ".",
                    ],
                    cwd=source,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=1800,
                )
            require(p.returncode == 0, "baseline_web_build_failed")
            self.baseline = json.loads(run(["docker", "image", "inspect", tag]).stdout)[
                0
            ]["Id"]
            R.inspect_image(
                self.baseline,
                "web",
                source_record,
                built_at,
                "https://api.staging.example.com/api/v1",
            )
            self.summary["baseline_source_sha256"] = source_hash
            self.before_caddy = local_caddy((source / "deploy/Caddyfile").read_text())
        self.summary["baseline_web_image"] = self.baseline
        self.after_caddy = local_caddy((ROOT / "deploy/Caddyfile").read_text())
        (private / "Caddyfile").write_text(self.before_caddy)
        # Never read a private dotenv. Every runtime value is authored here.
        env = {
            "DATABASE_URL": f"postgresql+psycopg://disposable:synthetic-test-only@db:5432/p5b_csp_{self.token}",
            "API_ENV": "staging",
            "ASK4MO_CSP_DISPOSABLE": self.token,
            "EMAIL_PROVIDER": "memory",
            "FRONTEND_ORIGINS": "https://app.staging.example.com",
            "APP_BASE_URL": "https://app.staging.example.com",
            "DOCUMENT_STORAGE_DIR": "/data/documents",
            "COPILOT_DATA_DIR": "/data/knowledge",
            "SESSION_SECRET": secrets.token_hex(32),
            "RATE_LIMIT_KEY_SECRET": secrets.token_hex(32),
            "PYTHON_DOTENV_DISABLED": "1",
            "TRUST_PROXY": "true",
            "OPS_MONITOR_ENABLED": "false",
            "OPENROUTER_API_KEY": "",
            "OPENAI_API_KEY": "",
            "BREVO_API_KEY": "",
            "AI_BUDGET_CONFIG_PATH": "",
        }
        (private / "runtime.env").write_text(
            "".join(k + "=" + v + "\n" for k, v in env.items())
        )
        (private / "runtime.env").chmod(0o600)
        labels = {LABEL: self.token}
        api = {
            "image": m["images"]["application"]["image_id"],
            "pull_policy": "never",
            "env_file": [str(private / "runtime.env")],
            "tmpfs": [
                "/data/knowledge:uid=10001,gid=10001,mode=0700",
                "/data/documents:uid=10001,gid=10001,mode=0700",
            ],
            "volumes": [f"{ROOT / 'scripts/csp/seed.py'}:/fixture/seed.py:ro"],
            "command": [
                "uvicorn",
                "src.api.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--no-access-log",
                "--log-level",
                "warning",
            ],
            "depends_on": {"migrate": {"condition": "service_completed_successfully"}},
        }
        migrate = {
            "image": api["image"],
            "pull_policy": "never",
            "env_file": api["env_file"],
            "command": ["bash", "scripts/migrate.sh"],
            "depends_on": {"db": {"condition": "service_healthy"}},
        }
        self.profile = {
            "services": {
                "db": {
                    "image": PG,
                    "environment": {
                        "POSTGRES_USER": "disposable",
                        "POSTGRES_PASSWORD": "synthetic-test-only",
                        "POSTGRES_DB": "p5b_csp_" + self.token,
                    },
                    "volumes": ["db:/var/lib/postgresql/data"],
                    "healthcheck": {
                        "test": ["CMD-SHELL", "pg_isready -U disposable"],
                        "interval": "2s",
                        "timeout": "2s",
                        "retries": 30,
                    },
                },
                "migrate": migrate,
                "api": api,
                "web": {"image": self.baseline, "pull_policy": "never"},
                "caddy": {
                    "image": CADDY,
                    "environment": {
                        "APP_DOMAIN": "app.staging.example.com",
                        "API_DOMAIN": "api.staging.example.com",
                    },
                    "volumes": [
                        f"{private / 'Caddyfile'}:/etc/caddy/Caddyfile:ro",
                        "caddy:/data",
                        "caddy-config:/config",
                    ],
                    "depends_on": {
                        "web": {"condition": "service_started"},
                        "api": {"condition": "service_started"},
                    },
                },
            },
            "networks": {"default": {"internal": True, "labels": labels}},
            "volumes": {k: {"labels": labels} for k in ("db", "caddy", "caddy-config")},
        }
        for service in self.profile["services"].values():
            service.update(labels=labels, restart="no")
        self.summary["phase"] = "validate_disposable_compose"
        self.write_profile()
        # Validate the actual shipped Caddy configuration before service creation.
        for phase, policy in (
            ("before", self.before_caddy),
            ("after", self.after_caddy),
        ):
            self.summary["phase"] = "validate_caddy_" + phase
            (private / "Caddyfile").write_text(policy)
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "-e",
                    "APP_DOMAIN=app.staging.example.com",
                    "-e",
                    "API_DOMAIN=api.staging.example.com",
                    "-v",
                    f"{private / 'Caddyfile'}:/etc/caddy/Caddyfile:ro",
                    CADDY,
                    "caddy",
                    "validate",
                    "--config",
                    "/etc/caddy/Caddyfile",
                ]
            )
        (private / "Caddyfile").write_text(self.before_caddy)
        self.summary["caddy_validation"] = "before_and_after_PASS"

    def write_profile(self):
        (self.out / "private/compose.yml").write_text(
            yaml.safe_dump(self.profile, sort_keys=False)
        )
        resolved = json.loads(self.compose("config", "--format", "json").stdout)
        require(
            all(
                not s.get("ports") and not s.get("privileged")
                for s in resolved["services"].values()
            ),
            "private_topology_required",
        )
        require(
            resolved["networks"]["default"]["internal"], "internal_network_required"
        )

    def lifecycle_snapshot(self, label):
        # Optional diagnostics only: never retain inspect output, IDs, logs or errors.
        snapshot = {"label": label, "services": {}}
        for role in ("api", "web", "caddy"):
            evidence = {"available": False}
            try:
                cid = self.compose("ps", "-q", role, timeout=8).stdout.decode().strip()
                info = json.loads(run(["docker", "inspect", cid], timeout=8).stdout)[0]
                state = info.get("State", {})
                status = state.get("Status")
                health = (state.get("Health") or {}).get("Status", "none")
                evidence = {
                    "available": True,
                    "status": status if status in {"created", "running", "restarting", "exited", "dead", "paused"} else "unknown",
                    "health": health if health in {"starting", "healthy", "unhealthy", "none"} else "unknown",
                }
            except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.SubprocessError):
                pass
            snapshot["services"][role] = evidence
        self.summary.setdefault("lifecycle_diagnostics", []).append(snapshot)

    def ready(self):
        # Poll from the actual Caddy container on its own private network.
        for _ in range(90):
            p = self.compose(
                "exec",
                "-T",
                "api",
                "curl",
                "-fsS",
                "http://localhost:8000/api/v1/health",
                timeout=8,
                check=False,
            )
            w = self.compose(
                "exec",
                "-T",
                "web",
                "curl",
                "-fsS",
                "http://localhost:3000/sign-in",
                timeout=8,
                check=False,
            )
            if p.returncode == w.returncode == 0:
                return
            time.sleep(1)
        raise ValueError("auth_topology_not_live")

    def browser(self, phase):
        self.summary["phase"] = "browser_" + phase
        cid = self.compose("ps", "-q", "caddy").stdout.decode().strip()
        info = json.loads(run(["docker", "inspect", cid]).stdout)[0]
        addresses = [
            v["IPAddress"] for v in info["NetworkSettings"]["Networks"].values()
        ]
        require(
            len(addresses) == 1 and ipaddress.ip_address(addresses[0]).is_private,
            "private_edge_address_required",
        )
        env = dict(
            os.environ,
            CSP_PHASE=phase,
            CSP_EDGE_IP=addresses[0],
            CSP_CREDENTIALS=str(self.out / "private/credentials.json"),
            CSP_PRIVATE_RESULTS=str(self.out / "private/browser-results"),
            CSP_BROWSER_SUMMARY=str(self.out / f"browser-{phase}.json"),
        )
        result = run(
            [
                "npm",
                "--prefix",
                str(ROOT / "frontend"),
                "run",
                "e2e",
                "--",
                "--config",
                "csp/playwright.config.ts",
            ],
            env=env,
            timeout=120,
            check=False,
        )
        # Playwright failure call logs can contain form values. Discard raw output;
        # retain only the authored safe stage/policy/count evidence and exit status.
        self.summary[phase + "_browser_exit"] = result.returncode
        summary = self.out / f"browser-{phase}.json"
        self.summary[phase] = (
            json.loads(summary.read_text())
            if summary.exists()
            else {"passed": False, "stage": "browser_process_before_test"}
        )
        return result.returncode == 0 and self.summary[phase].get("passed") is True

    def execute(self):
        self.summary["phase"] = "start_disposable_auth_topology"
        self.created = True
        self.compose("up", "-d", "caddy", timeout=180)
        self.lifecycle_snapshot("baseline_started")
        self.ready()
        self.lifecycle_snapshot("baseline_ready")
        self.summary["phase"] = "seed_synthetic_invited_account"
        credentials = self.compose(
            "exec", "-T", "api", "python", "/fixture/seed.py"
        ).stdout
        account = json.loads(credentials)
        path = self.out / "private/credentials.json"
        path.write_text(json.dumps(account))
        path.chmod(0o600)
        before_passed = self.browser("before")
        self.compose("stop", "web", "caddy")
        self.profile["services"]["web"]["image"] = self.summary["images"]["web"]
        (self.out / "private/Caddyfile").write_text(self.after_caddy)
        self.write_profile()
        self.compose("up", "-d", "--force-recreate", "web", "caddy")
        self.lifecycle_snapshot("hardened_started")
        self.ready()
        self.lifecycle_snapshot("hardened_ready")
        after_passed = self.browser("after")
        require(
            before_passed and after_passed, "before_after_browser_qualification_failed"
        )
        raw = self.compose("logs", "--no-color").stdout
        require(
            all(value.encode() not in raw for value in account.values()),
            "synthetic_credentials_in_service_logs",
        )
        self.summary["log_privacy"] = {
            "credentials_found": False,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        head = (
            self.compose(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "disposable",
                "-d",
                "p5b_csp_" + self.token,
                "-Atc",
                "SELECT version_num FROM alembic_version",
            )
            .stdout.decode()
            .splitlines()
        )
        require_database_head(head, self.expected_schema)
        self.summary["schema"] = head[0]
        for role in ("api", "web"):
            cid = self.compose("ps", "-q", role).stdout.decode().strip()
            actual = json.loads(run(["docker", "inspect", cid]).stdout)[0]["Image"]
            require(
                actual
                == self.summary["images"]["application" if role == "api" else "web"],
                "running_image_mismatch",
            )
        self.summary["non_root_users"] = {
            role: self.compose("exec", "-T", role, "id", "-u").stdout.decode().strip()
            for role in ("api", "web")
        }
        require(
            self.summary["non_root_users"] == {"api": "10001", "web": "1000"},
            "non_root_identity_mismatch",
        )
        self.summary["scope"] = "Caddy_Next_FastAPI_PG_auth_only_not_full_campaign"
        self.summary["phase"] = "complete"
        self.summary["result"] = "PASS"

    def cleanup(self):
        if not self.created:
            return
        # Refuse deletion if any resource in this Compose project lacks its own label.
        for resource in ("container", "volume", "network"):
            ids = (
                run(
                    [
                        "docker",
                        resource,
                        "ls",
                        *(["-a"] if resource == "container" else []),
                        "-q",
                        "--filter",
                        "label=com.docker.compose.project=" + self.project,
                    ]
                )
                .stdout.decode()
                .split()
            )
            for identity in ids:
                item = json.loads(
                    run(["docker", resource, "inspect", identity]).stdout
                )[0]
                labels = (
                    item["Config"]["Labels"]
                    if resource == "container"
                    else item["Labels"]
                )
                require(labels.get(LABEL) == self.token, "cleanup_label_mismatch")
        self.compose("down", "--volumes", "--remove-orphans", timeout=90)
        self.summary["cleanup"] = "owned_project_only_PASS"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-disposable", action="store_true", required=True)
    for name in ("manifest", "anchor", "sha", "out"):
        parser.add_argument("--" + name, required=True)
    check = Check(parser.parse_args())
    try:
        check.prepare()
        check.execute()
    except Exception as exc:
        # Bounded code only: never serialize external exception/credential payloads.
        check.summary["failure_class"] = type(exc).__name__
        import re

        if type(exc) is ValueError and re.fullmatch(r"[a-z_]{1,80}", str(exc)):
            check.summary["failure_code"] = str(exc)
    finally:
        try:
            check.cleanup()
        except Exception:
            check.summary.update(result="FAIL", cleanup="FAILED_REFUSED")
        if check.owns_output:
            (check.out / "summary.json").write_text(
                json.dumps(check.summary, indent=2, sort_keys=True)
            )
    print(json.dumps({"result": check.summary["result"], "scope": "disposable_csp"}))
    return 0 if check.summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
