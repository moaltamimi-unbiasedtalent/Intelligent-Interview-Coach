#!/usr/bin/env python3
"""Disposable connected privacy request qualification; no real data or providers."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.e2e import journey_stack as stack  # noqa: E402
from scripts.e2e import story_bank_connected as story  # noqa: E402


def serve(args):
    from src.auth_repository import AccountRepository
    seed = story._seed

    def verified(sf, state, count):
        seed(sf, state, count)
        for account in json.loads((state / "accounts.json").read_text()).values():
            AccountRepository(sf).mark_email_verified(account["id"])

    story._seed = verified
    return story.serve(args)


def valid_facts(value):
    expected = {"submissions": 2, "owner_isolation": True, "reload": True, "fresh_session": True, "refusals": 6, "unchanged": True}
    return (isinstance(value, dict) and set(value) == set(expected)
            and all(type(value[k]) is type(v) and value[k] == v for k, v in expected.items()))


def stable_snapshot(state):
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        users = db.execute("SELECT id,subject,provider,display_name,email,platform_role,status,email_verified,onboarding_completed_at,onboarding_step FROM users ORDER BY id").fetchall()
        tables = ("user_preferences", "candidate_stories", "opportunities", "jobs")
        contents = {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in tables}
    return users, contents


def run(args):
    stack._check_ports(args.api_port, args.web_port)
    api = web = None
    with tempfile.TemporaryDirectory(prefix="ask4mo_story_connected_") as tmp:
        state = Path(tmp)
        font = state / "font.cjs"
        font.write_text("module.exports = new Proxy({}, {get: () => `/* latin */\\n@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; src: url(mock.woff2) format('woff2'); }`});\n")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(state), "TMPDIR": tempfile.gettempdir(),
               "PYTHON_DOTENV_DISABLED": "1", "ASK4MO_PROVIDER_MODE": "offline", "NEXT_TELEMETRY_DISABLED": "1",
               "NEXT_FONT_GOOGLE_MOCKED_RESPONSES": str(font), "NEXT_DIST_DIR": ".next",
               "NEXT_PUBLIC_API_BASE_URL": f"http://localhost:{args.api_port}/api/v1"}
        cache = Path.home() / ("Library/Caches/ms-playwright" if platform.system() == "Darwin" else ".cache/ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(cache))
        frontend = ROOT / "frontend"
        try:
            with (state / "api.log").open("w") as log:
                api = subprocess.Popen([sys.executable, str(Path(__file__)), "serve", "--state-dir", str(state), "--api-port", str(args.api_port), "--web-port", str(args.web_port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                stack._wait(f"http://127.0.0.1:{args.api_port}/api/v1/health", 90, "API")
                before = stable_snapshot(state)
                subprocess.run(["npm", "run", "build"], cwd=frontend, env=env, check=True)
                with (state / "web.log").open("w") as web_log:
                    web = subprocess.Popen(["npx", "next", "start", "-p", str(args.web_port)], cwd=frontend, env=env, stdout=web_log, stderr=subprocess.STDOUT, start_new_session=True)
                    stack._wait(f"http://localhost:{args.web_port}/", 60, "web")
                    out = state / "results"
                    out.mkdir()
                    pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", STORY_API_URL=f"http://localhost:{args.api_port}/api/v1", STORY_ACCOUNTS_FILE=str(state / "accounts.json"), STORY_OUTPUT_DIR=str(out))
                    result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.privacy-request-connected.config.ts", "--reporter=json"], cwd=frontend, env=pw_env, capture_output=True)
                    if result.returncode:
                        try:
                            report = json.loads(result.stdout)
                            def locations(node):
                                if isinstance(node, dict):
                                    for error in node.get("errors", []):
                                        loc = error.get("location") or {}
                                        if str(loc.get("file", "")).endswith("intake.spec.ts") and isinstance(loc.get("line"), int):
                                            print(f"Synthetic browser failure at intake.spec.ts:{loc['line']}")
                                    for value in node.values(): locations(value)
                                elif isinstance(node, list):
                                    for value in node: locations(value)
                            locations(report)
                        except (ValueError, TypeError):
                            pass
                        print("Privacy request connected: FAIL (raw browser output withheld)")
                        return result.returncode
                    facts_path = out / "privacy-facts.json"
                    if not facts_path.is_file() or facts_path.stat().st_size > 1024:
                        raise AssertionError("missing bounded facts")
                    facts = json.loads(facts_path.read_text())
                    if not valid_facts(facts):
                        raise AssertionError("invalid bounded facts")
                    accounts = json.loads((state / "accounts.json").read_text())
                    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
                        rows = db.execute("SELECT user_id,subject_user_id,request_type,source,request_note,status,result_category,completed_at,related_job_public_id FROM privacy_requests ORDER BY user_id").fetchall()
                        jobs = db.execute("SELECT count(*) FROM jobs").fetchone()[0]
                    expected = sorted([(accounts["owner"]["id"], accounts["owner"]["id"], "correction", "candidate_portal", "SYNTHETIC correction alpha", "submitted", None, None, None), (accounts["other"]["id"], accounts["other"]["id"], "correction", "candidate_portal", "SYNTHETIC correction beta", "submitted", None, None, None)])
                    if rows != expected or jobs:
                        raise AssertionError("disposable persistence or job state mismatch")
                    if stable_snapshot(state) != before:
                        raise AssertionError("account, profile, content, or job state changed")
                    print("Privacy request connected: 1 PASS; 2 submissions; 6 refusals; owner isolation, reload, fresh session and disposable persistence PASS")
                    return 0
        finally:
            stack._stop_owned_process_group(web)
            stack._stop(api)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18458)
    p.add_argument("--web-port", type=int, default=13458)
    p.add_argument("--state-dir")
    args = p.parse_args()
    if args.mode == "serve":
        state = Path(args.state_dir).resolve() if args.state_dir else None
        if not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not state.name.startswith("ask4mo_story_connected_") or not state.is_dir() or (state / "journey.db").exists():
            raise SystemExit("fresh disposable test directory required")
        return serve(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
