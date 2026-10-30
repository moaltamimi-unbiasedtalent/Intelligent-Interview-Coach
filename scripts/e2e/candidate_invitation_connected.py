#!/usr/bin/env python3
"""Run the synthetic Candidate user journey on an isolated, loopback-only local stack.

Creates its own temporary SQLite database, processes and browser contexts. No hosted
services, provider credentials, real identities, or original persistence are used.
"""
from __future__ import annotations

import argparse
import os
import platform
import socket
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.e2e import journey_stack as stack  # noqa: E402


def serve(args: argparse.Namespace) -> int:
    # This test-only process may connect only to itself; it has no external provider path.
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def allowed(address):
        if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("connected Candidate test refuses non-loopback network")

    def connect(sock, address):
        allowed(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        allowed(address)
        return original_connect_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    return stack.serve(argparse.Namespace(state_dir=args.state_dir, variant="healthy", api_port=args.api_port,
                                          web_port=args.web_port, invitations=2))


def run(args: argparse.Namespace) -> int:
    stack._check_ports(args.api_port, args.web_port)
    api = web = None
    with tempfile.TemporaryDirectory(prefix="ask4mo_candidate_connected_") as tmp:
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
                    pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", CANDIDATE_API_URL=f"http://localhost:{args.api_port}/api/v1",
                                  JOURNEY_INVITATIONS_FILE=str(state / "invitations.json"))
                    result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.candidate-connected.config.ts"], cwd=frontend, env=pw_env).returncode
                    if result:
                        return result
                    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
                        rows = db.execute("SELECT email FROM users WHERE email IN (?, ?, ?)",
                                          ("missing@example.test", "invalid@example.test", "replay@example.test")).fetchall()
                        if rows:
                            raise AssertionError("refused synthetic registrations persisted accounts")
                    return 0
        finally:
            stack._stop(web)
            stack._stop(api)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18443)
    p.add_argument("--web-port", type=int, default=13443)
    p.add_argument("--state-dir")
    args = p.parse_args()
    if args.mode == "serve":
        state = Path(args.state_dir).resolve() if args.state_dir else None
        if (not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve())
                or not state.name.startswith("ask4mo_candidate_connected_") or not state.is_dir()
                or (state / "journey.db").exists()):
            raise SystemExit("serve requires a fresh isolated Candidate test directory")
        return serve(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
