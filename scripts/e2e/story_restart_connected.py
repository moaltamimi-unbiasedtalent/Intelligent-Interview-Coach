#!/usr/bin/env python3
"""Synthetic, loopback-only graceful API restart using one runner-owned database."""
from __future__ import annotations
import argparse
import json
import os
import platform
import signal
import socket
import stat
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.e2e import journey_stack as stack  # noqa: E402
from scripts.e2e import story_bank_connected as story  # noqa: E402


def validate_owned(state, expected, *, resume):
    state = Path(state)
    temp = Path(tempfile.gettempdir()).resolve()
    if state.is_symlink() or state.resolve().parent != temp or not state.name.startswith("ask4mo_restart_") or not state.is_dir():
        raise ValueError("unowned restart state")
    metadata = state.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError("restart state is not private and owned")
    db = state / "journey.db"
    if db.is_symlink() or db.resolve().parent != state.resolve():
        raise ValueError("unowned database path")
    if resume:
        if not db.is_file():
            raise ValueError("missing owned database")
        st = db.stat()
        if [st.st_dev, st.st_ino] != expected:
            raise ValueError("database identity mismatch")
    elif db.exists():
        raise ValueError("fresh database already exists")
    return state.resolve()


def serve(args):
    # The parent sends only its own state and original inode through an inherited pipe.
    with os.fdopen(args.control_fd, "r") as pipe:
        control = json.load(pipe)
    if control.get("parent") != os.getppid() or control.get("phase") not in ("initial", "resume"):
        raise ValueError("unowned process control")
    resume = control["phase"] == "resume"
    state = validate_owned(control["state"], control.get("identity"), resume=resume)
    if not resume:
        return story.serve(argparse.Namespace(state_dir=str(state), api_port=args.api_port, web_port=args.web_port))
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def allowed(address):
        if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("restart qualification refuses non-loopback network")

    def connect(sock, address):
        allowed(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        allowed(address)
        return original_connect_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex

    def no_seed(*_args, **_kwargs):
        raise RuntimeError("resume must never seed")

    stack._issue_invitations = no_seed
    return stack.serve(argparse.Namespace(state_dir=str(state), variant="healthy", api_port=args.api_port,
                                          web_port=args.web_port, invitations=0, resume_existing=True))


def start_api(state, args, phase, identity, env, log):
    read_fd, write_fd = os.pipe()
    try:
        proc = subprocess.Popen([sys.executable, str(Path(__file__)), "serve", "--control-fd", str(read_fd), "--api-port", str(args.api_port), "--web-port", str(args.web_port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, pass_fds=(read_fd,))
        os.close(read_fd)
        read_fd = -1
        with os.fdopen(write_fd, "w") as pipe:
            json.dump({"parent": os.getpid(), "state": str(state), "phase": phase, "identity": identity}, pipe)
        write_fd = -1
        return proc
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def ready(proc, port, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("owned API exited before readiness")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)  # bounded readiness polling, no mutation
    raise RuntimeError("owned API readiness failed")


def graceful_stop(proc, port):
    if proc is None or proc.poll() is not None:
        raise RuntimeError("original API not live")
    proc.send_signal(signal.SIGTERM)
    try:
        status = proc.wait(timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("original API did not stop gracefully") from exc
    if status not in (0, -signal.SIGTERM):
        raise RuntimeError("original API exited abnormally")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("old listener still serving")
    return True


def snapshot(state):
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in ("users", "candidate_stories", "opportunities")}


def valid_after_facts(facts):
    expected = {"owner": True, "other": True, "isolation": True, "foreign_read": 404, "foreign_edit": 404, "unchanged": True}
    return (isinstance(facts, dict) and set(facts) == set(expected)
            and all(type(facts[k]) is type(v) and facts[k] == v for k, v in expected.items()))


def same_snapshot(before, after):
    return bool(before) and before == after


def verify_ownership(state):
    ids = json.loads((state / "restart-private.json").read_text())
    accounts = json.loads((state / "accounts.json").read_text())
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        stories = db.execute("SELECT id,user_id,opportunity_id,status FROM candidate_stories ORDER BY id").fetchall()
        opportunities = db.execute("SELECT id,user_id FROM opportunities ORDER BY id").fetchall()
        users = db.execute("SELECT count(*) FROM users").fetchone()[0]
    expected = sorted([(ids["id"], accounts["owner"]["id"], ids["oppId"], "user_created"),
                       (ids["otherId"], accounts["other"]["id"], None, "user_created")])
    return users == 2 and stories == expected and opportunities == [(ids["oppId"], accounts["owner"]["id"])]


def phase_result(result):
    if result.returncode:
        return False
    try:
        stats = json.loads(result.stdout)["stats"]
    except (ValueError, KeyError, TypeError):
        return False
    return (type(stats.get("expected")) is int and stats["expected"] == 1
            and type(stats.get("unexpected")) is int and stats["unexpected"] == 0
            and type(stats.get("skipped")) is int and stats["skipped"] == 0)


def run(args):
    stack._check_ports(args.api_port, args.web_port)
    api = web = None
    with tempfile.TemporaryDirectory(prefix="ask4mo_restart_") as tmp:
        state = Path(tmp)
        font = state / "font.cjs"
        font.write_text("module.exports = new Proxy({}, {get: () => `/* latin */\\n@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; src: url(mock.woff2) format('woff2'); }`});\n")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(state), "TMPDIR": tempfile.gettempdir(), "PYTHON_DOTENV_DISABLED": "1", "ASK4MO_PROVIDER_MODE": "offline", "NEXT_TELEMETRY_DISABLED": "1", "NEXT_FONT_GOOGLE_MOCKED_RESPONSES": str(font), "NEXT_DIST_DIR": ".next", "NEXT_PUBLIC_API_BASE_URL": f"http://localhost:{args.api_port}/api/v1"}
        cache = Path.home() / ("Library/Caches/ms-playwright" if platform.system() == "Darwin" else ".cache/ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(cache))
        frontend = ROOT / "frontend"
        try:
            with (state / "api.log").open("w") as log, (state / "web.log").open("w") as web_log:
                validate_owned(state, None, resume=False)
                api = start_api(state, args, "initial", None, env, log)
                ready(api, args.api_port)
                db_stat = (state / "journey.db").stat()
                identity = [db_stat.st_dev, db_stat.st_ino]
                subprocess.run(["npm", "run", "build"], cwd=frontend, env=env, check=True)
                web = subprocess.Popen(["npx", "next", "start", "-p", str(args.web_port)], cwd=frontend, env=env, stdout=web_log, stderr=subprocess.STDOUT, start_new_session=True)
                stack._wait(f"http://localhost:{args.web_port}/", 60, "web")
                pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", STORY_API_URL=f"http://localhost:{args.api_port}/api/v1", STORY_ACCOUNTS_FILE=str(state / "accounts.json"), RESTART_STATE_DIR=str(state))
                def browser_phase(phase):
                    result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.story-restart-connected.config.ts", "--reporter=json"], cwd=frontend, env=dict(pw_env, RESTART_PHASE=phase), capture_output=True)
                    if not phase_result(result):
                        print(f"Story restart {phase}: FAIL (raw output withheld)")
                        raise RuntimeError("browser phase failed")
                browser_phase("before")
                if not (state / "restart-private.json").is_file():
                    raise RuntimeError("missing pre-restart evidence")
                if not verify_ownership(state):
                    raise RuntimeError("owned story fixtures mismatch")
                baseline = snapshot(state)
                graceful_stop(api, args.api_port)
                old_pid = api.pid
                api = None
                validate_owned(state, identity, resume=True)
                api = start_api(state, args, "resume", identity, env, log)
                if api.pid == old_pid:
                    raise RuntimeError("replacement process identity invalid")
                ready(api, args.api_port)
                validate_owned(state, identity, resume=True)
                if not same_snapshot(baseline, snapshot(state)):
                    raise RuntimeError("restart altered protected story records")
                browser_phase("after")
                facts_path = state / "after-facts.json"
                if not facts_path.is_file() or facts_path.stat().st_size > 512 or not valid_after_facts(json.loads(facts_path.read_text())):
                    raise RuntimeError("missing or invalid post-restart evidence")
                if not same_snapshot(baseline, snapshot(state)) or not verify_ownership(state):
                    raise RuntimeError("post-restart actions altered protected story records")
                graceful_stop(api, args.api_port)
                api = None
                stack._stop_owned_process_group(web)
                web = None
                print("Story restart connected: 1 scenario, 2 browser phases PASS; old API stopped; replacement ready; same owned DB; no reseed; snapshot unchanged; foreign read/edit 404; cleanup PASS")
                return 0
        finally:
            stack._stop_owned_process_group(web)
            if api is not None and api.poll() is None:
                api.kill()
                api.wait(timeout=10)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18468)
    p.add_argument("--web-port", type=int, default=13468)
    p.add_argument("--control-fd", type=int)
    args = p.parse_args()
    return serve(args) if args.mode == "serve" else run(args)


if __name__ == "__main__":
    raise SystemExit(main())
