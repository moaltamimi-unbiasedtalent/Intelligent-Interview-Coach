#!/usr/bin/env python3
"""Opt-in Linux-only built-image CSP regression. No registry, live provider or private env.

Builds the pinned pre-fix frontend from committed main and compares it with the
verified candidate release. Only a synthetic PostgreSQL/auth fixture is seeded.
"""

from __future__ import annotations
import argparse
import errno
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import socket
import ssl
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
EDGE_ORIGINS = (
    ("app.staging.example.com", "/sign-in", "web"),
    ("api.staging.example.com", "/api/v1/health", "api"),
)
READINESS_ATTEMPTS = 45
READINESS_SECONDS = 90
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(cidr) for cidr in
                         ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
EDGE_FAILURES = frozenset({"edge_tls_unavailable", "edge_http_unavailable",
                           "edge_route_mismatch", "edge_not_stable",
                           "edge_deadline_exceeded", "edge_deadline_guard_unavailable"})


class EdgeDeadlineExceeded(TimeoutError):
    pass


def remaining(deadline, cap=2):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise EdgeDeadlineExceeded("edge_deadline_exceeded")
    return min(cap, seconds)


def edge_failure(error):
    # Only authored classifications may cross the diagnostic boundary.
    if isinstance(error, EdgeDeadlineExceeded):
        return "edge_deadline_exceeded"
    return str(error) if type(error) is ValueError and str(error) in EDGE_FAILURES else "edge_route_mismatch"


def private_edge_address(address):
    try:
        ip = ipaddress.ip_address(address)
        return ip.version == 4 and any(ip in network for network in PRIVATE_NETWORKS)
    except ValueError:
        return False


# The probe never owns process signal state. Each wait and each progress step
# consumes the same absolute budget; readiness does not renew it.
HEADER_LIMIT = 16 * 1024
CHUNK_METADATA_LIMIT = 16 * 1024
API_BODY_LIMIT = 4096
HTML_BODY_LIMIT = 256 * 1024
WIRE_LIMIT = 1024 * 1024
BIO_LIMIT = 64 * 1024


class _EdgeTransport:
    """One raw descriptor; SSLObject and PollSelector own no network descriptor.

    Allocate the Python socket *object* before initializing its descriptor. The
    lifetime guards in edge_probe are established before __init__ can acquire an
    OS resource, including the C-call return / Python assignment interruption gap.
    """

    def __init__(self, context, hostname, deadline):
        self.raw = socket.socket.__new__(socket.socket)
        self.raw._io_refs, self.raw._closed = 0, True
        self.deadline = deadline
        self.incoming, self.outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.tls = context.wrap_bio(self.incoming, self.outgoing,
                                    server_side=False, server_hostname=hostname)
        self.wire = 0
        self.clean_eof = False

    def check(self):
        remaining(self.deadline)
        require(self.incoming.pending <= BIO_LIMIT and self.outgoing.pending <= BIO_LIMIT,
                "edge_http_unavailable")

    def close(self):
        # Idempotent, local-only close. No TLS shutdown, makefile, FD duplication,
        # worker, pool, finalizer or network-dependent cleanup.
        self.raw.close()

    def wait(self, events):
        self.check()
        with selectors.PollSelector() as poll:
            poll.register(self.raw, events)
            ready = poll.select(remaining(self.deadline))
        self.check()
        if not ready:
            raise EdgeDeadlineExceeded("edge_deadline_exceeded")

    def connect(self, address):
        self.check()
        socket.socket.__init__(self.raw, socket.AF_INET, socket.SOCK_STREAM)
        self.check()
        self.raw.setblocking(False)
        self.check()
        code = self.raw.connect_ex((address, 443))
        self.check()
        if code in (errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY, errno.EINTR):
            self.wait(selectors.EVENT_WRITE)
            code = self.raw.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            self.check()
        require(code == 0, "edge_http_unavailable")

    def flush(self):
        self.check()
        while self.outgoing.pending:
            data = self.outgoing.read(min(self.outgoing.pending, 16384))
            self.check()
            view = memoryview(data)
            while view:
                self.check()
                require(self.wire + len(view) <= WIRE_LIMIT, "edge_http_unavailable")
                try:
                    sent = self.raw.send(view)
                except (BlockingIOError, InterruptedError):
                    self.wait(selectors.EVENT_WRITE)
                    continue
                self.check()
                require(0 < sent <= len(view), "edge_http_unavailable")
                self.wire += sent
                view = view[sent:]

    def receive(self):
        self.check()
        # One extra byte is not read beyond either resource bound.
        capacity = min(16384, BIO_LIMIT - self.incoming.pending, WIRE_LIMIT - self.wire)
        require(capacity > 0, "edge_http_unavailable")
        while True:
            try:
                data = self.raw.recv(capacity)
                break
            except (BlockingIOError, InterruptedError):
                self.wait(selectors.EVENT_READ)
        self.check()
        if not data:
            self.incoming.write_eof()
        else:
            self.wire += len(data)
            self.incoming.write(data)
        self.check()
        return bool(data)

    def operate(self, operation):
        # A WANT_WRITE without pending output cannot advance. Likewise a peer
        # EOF cannot be supplied repeatedly. Neither case may busy-spin.
        while True:
            self.check()
            try:
                value = operation()
            except ssl.SSLWantWriteError:
                require(self.outgoing.pending > 0, "edge_http_unavailable")
                self.flush()
            except ssl.SSLWantReadError:
                self.flush()
                require(not self.incoming.eof, "edge_http_unavailable")
                self.receive()
            else:
                self.check()
                self.flush()
                return value

    def request(self, path, hostname):
        self.operate(self.tls.do_handshake)
        require(self.tls.selected_alpn_protocol() in (None, "http/1.1"), "edge_tls_unavailable")
        data = (f"GET {path} HTTP/1.1\r\nHost: {hostname}\r\n"
                "Connection: close\r\nAccept-Encoding: identity\r\n\r\n").encode("ascii")
        while data:
            sent = self.operate(lambda: self.tls.write(data))
            require(0 < sent <= len(data), "edge_http_unavailable")
            data = data[sent:]

    def read(self, size):
        try:
            data = self.operate(lambda: self.tls.read(min(size, 16384)))
        except ssl.SSLZeroReturnError:
            data = b""
        if not data:
            # Only SSLObject's authenticated close_notify is EOF. A raw socket
            # loss raises SSLEOFError, including for close-delimited HTTP.
            self.clean_eof = True
        return data


    def finish_response(self):
        """Prove one complete response, not just its declared HTTP body.

        The fixed request asks the peer to close. A one-byte TLS read must reach
        authenticated close_notify without returning plaintext; then the raw
        transport must reach EOF without any further encrypted bytes. Neither a
        quiet poll nor a parser boundary establishes completion. All steps keep
        the original deadline and existing BIO/wire limits. No TLS shutdown is
        initiated and cleanup remains local-only.
        """
        self.check()
        require(self.read(1) == b"", "edge_http_unavailable")
        self.check()
        require(self.clean_eof and self.tls.pending() == 0 and self.incoming.pending == 0,
                "edge_http_unavailable")
        if not self.incoming.eof:
            require(not self.receive(), "edge_http_unavailable")
        self.check()
        require(self.incoming.eof and self.incoming.pending == 0 and self.outgoing.pending == 0,
                "edge_http_unavailable")


class _ProbeInput:
    """Small bounded plaintext adapter; makefile returns this, never a socket FD."""

    def __init__(self, transport):
        self.transport, self.buffer = transport, bytearray()
        self.headers = True
        self.header_bytes = 0
        self.first_line = True

    def makefile(self, mode):
        require(mode == "rb", "edge_http_unavailable")
        return self

    def flush(self):
        pass  # Read-only adapter; IOBase.close calls flush.

    def close(self):
        pass  # HTTPResponse must not own or delay raw descriptor closure.

    def read(self, size=-1):
        require(size >= 0, "edge_http_unavailable")
        self.transport.check()
        while len(self.buffer) < size:
            data = self.transport.read(min(16384, size - len(self.buffer)))
            if not data:
                break
            self.buffer.extend(data)
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        self.transport.check()
        return data

    def readline(self, size=-1):
        limit = min(size if size >= 0 else HEADER_LIMIT + 1, HEADER_LIMIT + 1)
        line = bytearray()
        while len(line) < limit:
            char = self.read(1)
            if not char:
                break
            require(not self.headers or self.header_bytes + len(line) + 1 <= HEADER_LIMIT,
                    "edge_http_unavailable")
            line.extend(char)
            if char == b"\n":
                break
        require(line.endswith(b"\r\n"), "edge_http_unavailable")
        if self.headers:
            self.header_bytes += len(line)
            require(self.header_bytes <= HEADER_LIMIT, "edge_http_unavailable")
            if self.first_line:
                require(re.fullmatch(rb"HTTP/1\.[01] 200 [\x20-\x7e]*\r\n", line) is not None,
                        "edge_http_unavailable")
                self.first_line = False
            elif line == b"\r\n":
                self.headers = False
            else:
                require(re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+:[\x20-\x7e\t]*\r\n", line) is not None,
                        "edge_http_unavailable")
        return bytes(line)


class _ProbeResponse(http.client.HTTPResponse):
    """Restrict stdlib's permissive chunk parsing; no new HTTP connection stack."""

    def __init__(self, source):
        super().__init__(source)
        self.chunk_metadata = 0

    def _chunk_line(self):
        line = self.fp.readline(CHUNK_METADATA_LIMIT - self.chunk_metadata + 1)
        self.chunk_metadata += len(line)
        require(self.chunk_metadata <= CHUNK_METADATA_LIMIT, "edge_http_unavailable")
        return line

    def _read_next_chunk_size(self):
        line = self._chunk_line()
        require(re.fullmatch(rb"[0-9A-Fa-f]+\r\n", line) is not None, "edge_http_unavailable")
        # Refuse huge integers before conversion as well as oversized bodies.
        require(len(line) <= 10, "edge_http_unavailable")
        return int(line[:-2], 16)

    def _read_and_discard_trailer(self):
        require(self._chunk_line() == b"\r\n", "edge_http_unavailable")

    def _get_chunk_left(self):
        # Python 3.11 otherwise discards two bytes without checking CRLF.
        if self.chunk_left == 0:
            self.chunk_metadata += 2
            require(self.chunk_metadata <= CHUNK_METADATA_LIMIT, "edge_http_unavailable")
            require(self._safe_read(2) == b"\r\n", "edge_http_unavailable")
            self.chunk_left = None
        return super()._get_chunk_left()


def _probe_response(transport, role):
    source = _ProbeInput(transport)
    response = _ProbeResponse(source)
    try:
        response.begin()
        transport.check()
        require(response.status == 200 and response.version in (10, 11), "edge_http_unavailable")
        lengths = response.headers.get_all("Content-Length", [])
        codings = response.headers.get_all("Transfer-Encoding", [])
        require(len(lengths) <= 1 and len(codings) <= 1 and not (lengths and codings),
                "edge_http_unavailable")
        require(not lengths or re.fullmatch(r"[0-9]+", lengths[0]) is not None, "edge_http_unavailable")
        require(not codings or (response.version == 11 and codings[0].lower() == "chunked"),
                "edge_http_unavailable")
        require(response.headers.get_all("Content-Encoding", []) in ([], ["identity"]), "edge_http_unavailable")
        require(not response.headers.get_all("Upgrade") and not response.headers.get_all("Trailer"),
                "edge_http_unavailable")
        limit = API_BODY_LIMIT if role == "api" else HTML_BODY_LIMIT
        expected = int(lengths[0]) if lengths else None
        require(expected is None or expected <= limit, "edge_http_unavailable")
        body = bytearray()
        while True:
            transport.check()
            part = response.read(min(16384, limit + 1 - len(body)))
            transport.check()
            if not part:
                break
            body.extend(part)
            require(len(body) <= limit, "edge_http_unavailable")
        require(expected is None or len(body) == expected, "edge_http_unavailable")
        require(expected is not None or response.chunked or transport.clean_eof, "edge_http_unavailable")
        require(not source.buffer, "edge_http_unavailable")
        transport.finish_response()
        transport.check()
        mime = response.getheader("Content-Type", "").split(";", 1)[0].lower()
        if role == "web":
            valid = mime == "text/html" and b"<!doctype html" in body[:4096].lower()
        else:
            valid = (mime == "application/json" and isinstance(value := json.loads(body), dict)
                     and value.get("status") == "ok")
        return "ready" if valid else "edge_route_mismatch"
    finally:
        response.close()


def edge_probe(address, context, hostname, path, role, *, deadline=None):
    """One pinned verified HTTPS request, no signals, DNS, proxy or retry."""
    require((hostname, path, role) in EDGE_ORIGINS, "edge_route_mismatch")
    require(private_edge_address(address), "edge_route_mismatch")
    require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED, "edge_tls_unavailable")
    deadline = min(deadline, time.monotonic() + 2) if deadline is not None else time.monotonic() + 2
    try:
        remaining(deadline)
        transport = _EdgeTransport(context, hostname, deadline)
        # Both lifetime guards precede descriptor acquisition. A single interrupt
        # before/during the first close completes via the already active outer
        # guard; at the outer close the first close has already completed. These
        # are local resource guards, with no signal state or cancellation deferral.
        try:
            try:
                transport.connect(address)
                transport.request(path, hostname)
                return _probe_response(transport, role)
            finally:
                transport.close()
        finally:
            transport.close()
    except EdgeDeadlineExceeded:
        return "edge_deadline_exceeded"
    except ssl.SSLCertVerificationError as exc:
        return "edge_route_mismatch" if getattr(exc, "verify_code", None) == 62 else "edge_tls_unavailable"
    except ssl.SSLError:
        return "edge_tls_unavailable"
    except (OSError, http.client.HTTPException, ValueError, TypeError, OverflowError):
        return "edge_http_unavailable"


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
        self._phase_deadlines = {}
        self._phase_ready = {}
        self._browser_attempted = set()
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

    def lifecycle_snapshot(self, label, *, deadline=None):
        # Optional diagnostics only: never retain inspect output, IDs, logs or errors.
        snapshot = {"label": label, "services": {}}
        for role in ("api", "web", "caddy"):
            evidence = {"available": False}
            try:
                cid = self.compose("ps", "-q", role, timeout=8 if deadline is None else remaining(deadline, 8)).stdout.decode().strip()
                info = json.loads(run(["docker", "inspect", cid], timeout=8 if deadline is None else remaining(deadline, 8)).stdout)[0]
                if deadline is not None:
                    remaining(deadline)
                state = info.get("State", {})
                status = state.get("Status")
                health = (state.get("Health") or {}).get("Status", "none")
                evidence = {
                    "available": True,
                    "status": status if status in {"created", "running", "restarting", "exited", "dead", "paused"} else "unknown",
                    "health": health if health in {"starting", "healthy", "unhealthy", "none"} else "unknown",
                }
            except EdgeDeadlineExceeded:
                raise
            except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.SubprocessError):
                pass
            snapshot["services"][role] = evidence
        self.summary.setdefault("lifecycle_diagnostics", []).append(snapshot)

    def edge_binding(self, *, deadline=None):
        """Authenticate the owned running edge and its one internal network.

        Identities are used only in memory for stability checks, never diagnostics.
        """
        deadline = time.monotonic() + 8 if deadline is None else deadline
        cid = self.compose("ps", "-q", "caddy", timeout=remaining(deadline)).stdout.decode().strip()
        require(bool(cid) and len(cid.split()) == 1, "edge_http_unavailable")
        info = json.loads(run(["docker", "inspect", cid], timeout=remaining(deadline)).stdout)[0]
        labels = info["Config"]["Labels"]
        require(labels.get(LABEL) == self.token
                and labels.get("com.docker.compose.project") == self.project,
                "edge_route_mismatch")
        require(info["State"]["Status"] == "running", "edge_http_unavailable")
        networks = list(info["NetworkSettings"]["Networks"].values())
        require(len(networks) == 1, "edge_route_mismatch")
        address, network = networks[0]["IPAddress"], networks[0]["NetworkID"]
        require(private_edge_address(address), "edge_route_mismatch")
        actual = json.loads(run(["docker", "network", "inspect", network], timeout=remaining(deadline)).stdout)[0]
        require(actual["Internal"] is True and actual["Labels"].get(LABEL) == self.token,
                "edge_route_mismatch")
        remaining(deadline)
        return cid, network, address

    def edge_context(self, *, deadline=None):
        # Read only the disposable public CA, in memory. No private key, retained
        # certificate, system trust changes, public CA/DNS or TLS bypass is needed.
        deadline = time.monotonic() + 2 if deadline is None else deadline
        ca = self.compose("exec", "-T", "caddy", "cat",
                          "/data/caddy/pki/authorities/local/root.crt", timeout=remaining(deadline)).stdout
        require(isinstance(ca, bytes) and 0 < len(ca) <= 16384, "edge_tls_unavailable")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.set_alpn_protocols(["http/1.1"])
        context.load_verify_locations(cadata=ca.decode("ascii"))
        remaining(deadline)
        return context, hashlib.sha256(ca).digest()

    def loopback_ready(self, role, *, deadline=None):
        deadline = time.monotonic() + 6 if deadline is None else deadline
        path = {"api": "http://localhost:8000/api/v1/health",
                "web": "http://localhost:3000/sign-in"}[role]
        response = self.compose("exec", "-T", role, "curl", "-fsS", "--max-time",
                                str(remaining(deadline)), path,
                                timeout=remaining(deadline), check=False)
        cid = self.compose("ps", "-q", role, timeout=remaining(deadline)).stdout.decode().strip()
        state = json.loads(run(["docker", "inspect", cid], timeout=remaining(deadline)).stdout)[0]["State"]
        remaining(deadline)
        health = (state.get("Health") or {}).get("Status", "none")
        return response.returncode == 0 and state.get("Status") == "running" and health in {"healthy", "none"}

    def observe_endpoint(self, binding, evidence):
        previous = getattr(self, "_observed_endpoint", None)
        evidence["endpoint_changed"] |= previous is not None and previous != binding
        self._observed_endpoint = binding  # Private identity is never serialized.

    def edge_round(self, evidence, *, deadline):
        """Both browser-facing routes, bounded responses, stable edge identity."""
        remaining(deadline)
        binding = self.edge_binding(deadline=deadline)
        self.observe_endpoint(binding, evidence)
        try:
            remaining(deadline)
            context, ca_identity = self.edge_context(deadline=deadline)
        except EdgeDeadlineExceeded:
            return None, None, "edge_deadline_exceeded"
        except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError):
            return None, None, "edge_tls_unavailable"
        for hostname, path, role in EDGE_ORIGINS:
            remaining(deadline)
            result = edge_probe(binding[2], context, hostname, path, role, deadline=deadline)
            require(result in EDGE_FAILURES or result == "ready", "edge_route_mismatch")
            evidence["edge_" + role + "_ready"] = result == "ready"
            if result != "ready":
                return None, None, result
            remaining(deadline)
            observed = self.edge_binding(deadline=deadline)
            self.observe_endpoint(observed, evidence)
            if observed != binding:
                evidence["endpoint_changed"] = True
                return None, None, "edge_not_stable"
        remaining(deadline)
        return binding + (ca_identity,), context, "ready"

    def ready(self, phase="before"):
        # Internal HTTP health alone is insufficient. Require two complete HTTPS
        # observations across a polling interval before the one browser attempt.
        require(phase in {"before", "after"}, "invalid_browser_phase")
        require(phase not in self._phase_deadlines, "edge_not_stable")
        self.summary["phase"] = "edge_readiness_" + phase
        self._ready_edge = None
        self._observed_endpoint = None
        start = time.monotonic()
        deadline = start + READINESS_SECONDS
        self._phase_deadlines[phase] = deadline
        evidence = {"phase": phase, "attempts": 0, "elapsed_ms": 0, "api_loopback_ready": False,
                    "web_loopback_ready": False, "edge_web_ready": False,
                    "edge_api_ready": False, "endpoint_changed": False,
                    "stable_observations": 0, "last_failure": "edge_http_unavailable"}
        self.summary.setdefault("edge_readiness", []).append(evidence)
        previous = None
        last_qualified = None
        for attempt in range(READINESS_ATTEMPTS):
            if time.monotonic() >= deadline:
                evidence["last_failure"] = "edge_deadline_exceeded"
                break
            evidence.update(attempts=attempt + 1, api_loopback_ready=False,
                            web_loopback_ready=False, edge_web_ready=False, edge_api_ready=False)
            try:
                for role in ("api", "web"):
                    evidence[role + "_loopback_ready"] = self.loopback_ready(role, deadline=deadline)
                if all(evidence[role + "_loopback_ready"] for role in ("api", "web")):
                    binding, _, category = self.edge_round(evidence, deadline=deadline)
                else:
                    binding, category = None, "edge_http_unavailable"
                if binding is not None and category == "ready":
                    evidence["endpoint_changed"] |= last_qualified is not None and last_qualified != binding
                    last_qualified = binding
                    if previous == binding:
                        evidence["stable_observations"] += 1
                    else:
                        evidence["endpoint_changed"] |= previous is not None
                        evidence["stable_observations"] = 1
                    previous = binding
                    category = "edge_not_stable"
                    if evidence["stable_observations"] >= 2 and time.monotonic() - start < READINESS_SECONDS:
                        self._ready_edge = binding
                        self._phase_ready[phase] = binding
                        evidence.update(last_failure="none", elapsed_ms=self.readiness_elapsed(start))
                        return
                else:
                    previous = None
                    evidence["stable_observations"] = 0
            except (ValueError, KeyError, IndexError, TypeError, AttributeError, OSError, subprocess.SubprocessError) as exc:
                previous = None
                category = edge_failure(exc)
                evidence["stable_observations"] = 0
            evidence.update(last_failure=category, elapsed_ms=self.readiness_elapsed(start))
            if category == "edge_deadline_guard_unavailable":
                break
            if time.monotonic() >= deadline:
                evidence["last_failure"] = "edge_deadline_exceeded"
                break
            if attempt + 1 < READINESS_ATTEMPTS:
                try:
                    time.sleep(remaining(deadline, 1))
                except EdgeDeadlineExceeded:
                    evidence["last_failure"] = "edge_deadline_exceeded"
                    break
        if time.monotonic() >= deadline:
            evidence["last_failure"] = "edge_deadline_exceeded"
        evidence["elapsed_ms"] = self.readiness_elapsed(start)
        raise ValueError(evidence["last_failure"])

    @staticmethod
    def readiness_elapsed(start):
        return min(120000, max(0, int((time.monotonic() - start) * 1000)))

    def phase_deadline(self, phase):
        require(phase in self._phase_deadlines and phase in self._phase_ready, "edge_not_stable")
        deadline = self._phase_deadlines[phase]
        remaining(deadline)
        return deadline

    def browser_edge(self, phase):
        # No retry at handoff: an address change or loss of edge readiness is a
        # qualification failure, not permission to repoll or relaunch Chromium.
        evidence = {"phase": phase, "edge_web_ready": False, "edge_api_ready": False,
                    "endpoint_changed": False, "last_failure": "edge_not_stable"}
        self.summary.setdefault("browser_edge_handoffs", []).append(evidence)
        try:
            deadline = self.phase_deadline(phase)
            expected = self._phase_ready[phase]
            binding, _, category = self.edge_round(evidence, deadline=deadline)
            remaining(deadline)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, OSError, subprocess.SubprocessError) as exc:
            evidence["last_failure"] = edge_failure(exc)
            raise ValueError(evidence["last_failure"]) from None
        evidence["last_failure"] = category
        require(category == "ready", category)
        if binding != expected:
            evidence.update(last_failure="edge_not_stable", endpoint_changed=True)
            raise ValueError("edge_not_stable")
        evidence["last_failure"] = "none"
        return binding[2]

    def browser(self, phase):
        require(phase in {"before", "after"}, "invalid_browser_phase")
        require(phase not in self._browser_attempted, "edge_not_stable")
        self.summary["phase"] = "browser_" + phase
        address = self.browser_edge(phase)
        env = dict(
            os.environ,
            CSP_PHASE=phase,
            CSP_EDGE_IP=address,
            CSP_CREDENTIALS=str(self.out / "private/credentials.json"),
            CSP_PRIVATE_RESULTS=str(self.out / "private/browser-results"),
            CSP_BROWSER_SUMMARY=str(self.out / f"browser-{phase}.json"),
        )
        # Last check after handoff and environment preparation: successful
        # probes cannot authorize a process launch after the original deadline.
        remaining(self.phase_deadline(phase))
        self._browser_attempted.add(phase)
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
        # Project only the fixed diagnostic category; never copy an error string.
        events = self.summary[phase].get("diagnostics", {}).get("events", [])
        failures = [e for e in events if isinstance(e, dict) and e.get("kind") == "request_failed"]
        passed = result.returncode == 0 and self.summary[phase].get("passed") is True
        if not passed:
            self.summary[phase + "_transport"] = (
                "browser_network_changed" if any(e.get("failure_category") == "network_changed" for e in failures)
                else "browser_transport_unknown"
            )
        # Observe any network replacement during the one browser process. Never
        # retry navigation or relaunch it; even a passing browser cannot mask drift.
        try:
            stable = self.edge_binding() == self._phase_ready[phase][:3]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, OSError, subprocess.SubprocessError):
            stable = False
        self.summary[phase + "_edge_stable_after_browser"] = stable
        require(stable, "edge_not_stable")
        return passed

    def execute(self):
        self.summary["phase"] = "start_disposable_auth_topology"
        self.created = True
        self.compose("up", "-d", "caddy", timeout=180)
        self.lifecycle_snapshot("baseline_started")
        self.ready("before")
        self.lifecycle_snapshot("baseline_ready", deadline=self.phase_deadline("before"))
        self.summary["phase"] = "seed_synthetic_invited_account"
        credentials = self.compose(
            "exec", "-T", "api", "python", "/fixture/seed.py",
            timeout=remaining(self.phase_deadline("before"), 180)
        ).stdout
        remaining(self.phase_deadline("before"))
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
        self.ready("after")
        self.lifecycle_snapshot("hardened_ready", deadline=self.phase_deadline("after"))
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
