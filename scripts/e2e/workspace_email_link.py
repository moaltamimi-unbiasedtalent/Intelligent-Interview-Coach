#!/usr/bin/env python3
"""Run the synthetic Workspace journey on an isolated, loopback-only local stack.

Creates its own temporary SQLite database, processes and browser contexts. No hosted
services, provider credentials, real identities, or original persistence are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.e2e import journey_stack as stack  # noqa: E402

PASSWORD = "Synthetic-Workspace-Test-Password-42"
ACCOUNTS = {
    "owner": ("workspace-owner@example.test", "user"),
    "recipient": ("link-recipient@example.test", "user"),
    "wrong": ("link-wrong@example.test", "user"),
    "unverified": ("link-unverified@example.test", "user"),
    "expired": ("link-expired@example.test", "user"),
    "revoked": ("link-revoked@example.test", "user"),
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
        if name != "unverified":
            accounts.mark_email_verified(user_id)
        accounts.complete_onboarding(user_id)
        result[name] = {"id": user_id, "email": email}
    # Test-only bridge: the actual sender still captures mail in memory. Transfer only
    # synthetic links to a private, short-lived file; never expose an HTTP endpoint.
    from src.mail import MemoryEmailSender

    original_send = MemoryEmailSender.send
    by_email = {email: name for name, (email, _) in ACCOUNTS.items()}

    def capture(sender, message):
        accepted = original_send(sender, message)
        if message.category == "workspace_invitation":
            name = by_email.get(message.to)
            match = re.search(r"https?://[^\s]+/workspaces/accept\?token=[^\s]+", message.body)
            if not name or not match:
                raise RuntimeError("synthetic invitation capture failed")
            path = state / ("mail-" + name + ".json")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                json.dump({"link": match.group(0)}, out)
            if name == "expired":
                # Deterministic test fixture: modify only this disposable invitation.
                with sqlite3.connect(state / "journey.db") as db:
                    changed = db.execute("UPDATE workspace_invitations SET expires_at = ? WHERE email = ? AND status = 'pending'", ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), message.to)).rowcount
                    if changed != 1:
                        raise RuntimeError("disposable expiry fixture failed")
        return accepted

    MemoryEmailSender.send = capture
    path = state / "accounts.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    path.chmod(0o600)


def serve(args: argparse.Namespace) -> int:
    # This test-only process may connect only to itself; it has no external provider path.
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def allowed(address):
        if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("connected Workspace test refuses non-loopback network")

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
    with tempfile.TemporaryDirectory(prefix="ask4mo_workspace_email_link_") as tmp:
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
                    pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", LINK_API_URL=f"http://localhost:{args.api_port}/api/v1",
                                  LINK_ACCOUNTS_FILE=str(state / "accounts.json"), LINK_OUTPUT_DIR=str(state / "playwright-results"))
                    # The link is a credential even in a synthetic run. Raw Playwright output
                    # can contain URLs or form inputs, so keep it in memory and never publish it.
                    result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.workspace-email-link.config.ts"], cwd=frontend, env=pw_env, capture_output=True)
                    if result.returncode:
                        print("Connected email-link journey: FAIL (raw browser output withheld for token privacy)")
                        return result.returncode
                    print("Connected email-link journey: 1 PASS")
                    # Check the synthetic DB without emitting identifiers or tokens.
                    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
                        invitations = db.execute("SELECT email, status, token_hash, accepted_user_id FROM workspace_invitations").fetchall()
                        members = db.execute("SELECT user_id, role FROM workspace_memberships WHERE status = 'active'").fetchall()
                        audit = db.execute("SELECT event_type, actor_user_id, context FROM audit_events WHERE event_type LIKE 'workspace.%'").fetchall()
                    ids = json.loads((state / "accounts.json").read_text())
                    expected_members = {(ids["owner"]["id"], "workspace_owner"), (ids["recipient"]["id"], "workspace_member")}
                    if set(members) != expected_members or len(members) != 2 or sorted(row[1] for row in invitations) != ["accepted", "expired", "pending", "revoked"]:
                        raise AssertionError("refused invitations changed membership or invitation state")
                    if any(len(row[2]) != 64 or not re.fullmatch(r"[0-9a-f]{64}", row[2]) for row in invitations):
                        raise AssertionError("invitation token hashes invalid")
                    if any((row[1] == "accepted" and row[3] != ids["recipient"]["id"]) or (row[1] != "accepted" and row[3] is not None) for row in invitations):
                        raise AssertionError("invitation acceptance attribution invalid")
                    accepted = [(event, actor) for event, actor, _ in audit if event == "workspace.invite_accepted"]
                    if accepted != [("workspace.invite_accepted", ids["recipient"]["id"])]:
                        raise AssertionError("unexpected successful acceptance audit")
                    # Never print or retain mail payloads, raw links or audit records.
                    for path in state.glob("mail-*.json"):
                        token = parse_qs(urlsplit(json.loads(path.read_text())["link"]).query)["token"][0]
                        name = path.stem.removeprefix("mail-")
                        rows = [row for row in invitations if row[0] == ACCOUNTS[name][0]]
                        if len(rows) != 1 or rows[0][2] != hashlib.sha256(token.encode()).hexdigest():
                            raise AssertionError("stored invitation token hash did not match")
                        if token in json.dumps(audit) or any(token == row[2] for row in invitations):
                            raise AssertionError("raw token appeared in audit or stored invitations")
                        if any(token in (state / log).read_text(errors="replace") for log in ("api.log", "web.log")):
                            raise AssertionError("raw token appeared in local service logs")
                    print("Disposable invitation state, hash storage and successful-acceptance audit: PASS")
                    return 0
        finally:
            stack._stop(web)
            stack._stop(api)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18447)
    p.add_argument("--web-port", type=int, default=13447)
    p.add_argument("--state-dir")
    args = p.parse_args()
    if args.mode == "serve":
        state = Path(args.state_dir).resolve() if args.state_dir else None
        if (not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve())
                or not state.name.startswith("ask4mo_workspace_email_link_") or not state.is_dir()
                or (state / "journey.db").exists()):
            raise SystemExit("serve requires a fresh isolated Workspace test directory")
        return serve(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
