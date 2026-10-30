#!/usr/bin/env python3
"""Run the synthetic Admin user journey on an isolated, loopback-only local stack.

Creates its own temporary SQLite database, processes and browser contexts. No hosted
services, provider credentials, real identities, or original persistence are used.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.e2e import journey_stack as stack  # noqa: E402

PASSWORD = "Synthetic-Admin-Test-Password-42"
ACCOUNTS = {
    "admin": ("admin@example.test", "platform_admin"),
    "viewer": ("viewer@example.test", "support_operator"),
    "security": ("security@example.test", "security_privacy_admin"),
    "candidate": ("candidate@example.test", "user"),
}


def _seed(session_factory, state: Path, _count: int) -> None:
    from src.auth_repository import AccountRepository
    from src.authsec.passwords import hash_password

    accounts = AccountRepository(session_factory)
    result = {}
    for name, (email, role) in ACCOUNTS.items():
        user_id = accounts.create_password_account(email=email, password_hash=hash_password(PASSWORD), display_name=None)
        if user_id is None:
            raise RuntimeError("synthetic account creation failed")
        if role != "user":
            accounts.set_platform_role(user_id, role)
        accounts.complete_onboarding(user_id)
        result[name] = {"id": user_id, "email": email}
    from src.support_repository import SupportRepository
    SupportRepository(session_factory).create_ticket(
        owner_user_id=result["candidate"]["id"], category="account_login", subject="SYNTHETIC_PRIVATE_SENTINEL",
        message="SYNTHETIC_PRIVATE_SENTINEL", request_id=None, source_route=None, environment=None,
    )
    path = state / "accounts.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    path.chmod(0o600)


def serve(args: argparse.Namespace) -> int:
    # This test-only process may connect only to itself; it has no external provider path.
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def allowed(address):
        if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("connected Admin test refuses non-loopback network")

    def connect(sock, address):
        allowed(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        allowed(address)
        return original_connect_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    stack._issue_invitations = _seed
    return stack.serve(argparse.Namespace(state_dir=args.state_dir, variant="healthy", api_port=args.api_port,
                                          web_port=args.web_port, invitations=0))


def run(args: argparse.Namespace) -> int:
    stack._check_ports(args.api_port, args.web_port)
    api = web = None
    with tempfile.TemporaryDirectory(prefix="ask4mo_admin_connected_") as tmp:
        state = Path(tmp)
        # Mock the font download at build time, not application API responses.
        font = state / "font.cjs"
        font.write_text("module.exports = new Proxy({}, {get: () => `/* latin */\\n@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; src: url(mock.woff2) format('woff2'); }`});\n", encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(state), "TMPDIR": tempfile.gettempdir(),
               "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
               "PYTHON_DOTENV_DISABLED": "1", "ASK4MO_PROVIDER_MODE": "offline", "NEXT_TELEMETRY_DISABLED": "1",
               "NEXT_FONT_GOOGLE_MOCKED_RESPONSES": str(font), "NEXT_DIST_DIR": ".next",
               "NEXT_PUBLIC_API_BASE_URL": f"http://localhost:{args.api_port}/api/v1"}
        browser_cache = Path.home() / ("Library/Caches/ms-playwright" if platform.system() == "Darwin" else ".cache/ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(browser_cache))
        frontend = ROOT / "frontend"
        try:
            with (state / "api.log").open("w") as log:
                api = subprocess.Popen([sys.executable, str(Path(__file__)), "serve", "--state-dir", str(state), "--api-port", str(args.api_port),
                                        "--web-port", str(args.web_port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                stack._wait(f"http://127.0.0.1:{args.api_port}/api/v1/health", 90, "API")
                subprocess.run(["npm", "run", "build"], cwd=frontend, env=env, check=True)
                with (state / "web.log").open("w") as web_log:
                    web = subprocess.Popen(["npx", "next", "start", "-p", str(args.web_port)], cwd=frontend, env=env, stdout=web_log, stderr=subprocess.STDOUT)
                    stack._wait(f"http://localhost:{args.web_port}/", 60, "web")
                    pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", ADMIN_API_URL=f"http://localhost:{args.api_port}/api/v1",
                                  ADMIN_ACCOUNTS_FILE=str(state / "accounts.json"))
                    return subprocess.run(["npx", "playwright", "test", "--config", "playwright.admin-connected.config.ts"], cwd=frontend, env=pw_env).returncode
        finally:
            stack._stop(web)
            stack._stop(api)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18442)
    p.add_argument("--web-port", type=int, default=13442)
    p.add_argument("--state-dir")
    args = p.parse_args()
    if args.mode == "serve":
        state = Path(args.state_dir).resolve() if args.state_dir else None
        if (not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve())
                or not state.name.startswith("ask4mo_admin_connected_") or not state.is_dir()
                or (state / "journey.db").exists()):
            raise SystemExit("serve requires a fresh isolated Admin test directory")
        return serve(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
