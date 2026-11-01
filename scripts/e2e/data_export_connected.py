#!/usr/bin/env python3
"""Private synthetic Story Bank to Practice qualification; loopback only."""
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

SELECTED = "SYNTH_SELECTED_CEDAR"
UNSELECTED = "SYNTH_UNSELECTED_MAPLE"
FOREIGN = "SYNTH_FOREIGN_WILLOW"


def observe(messages, story_id: int) -> dict:
    """Convert transient synthetic model inputs to bounded facts, never prompt text."""
    text = "\n".join(str(item.get("content", "")) for item in messages)
    return {"selected": SELECTED in text, "unselected": UNSELECTED in text, "foreign": FOREIGN in text,
            "identity": f"[[STORY {story_id} BEGIN]]" in text, "unverified": "verification: unverified" in text,
            "candidate_account": "the candidate's own account" in text}


def qualifies(facts: dict) -> bool:
    return all(facts[k] for k in ("selected", "identity", "unverified", "candidate_account")) and not any(facts[k] for k in ("unselected", "foreign"))


def serve(args: argparse.Namespace) -> int:
    state = Path(args.state_dir)
    from scripts.e2e import journey_fakes as fixtures
    original = fixtures.FixtureChatClient.create_chat_completion

    def observed(client, **kwargs):
        with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
            rows = db.execute("SELECT id FROM candidate_stories WHERE title = ?", ("Selected synthetic story",)).fetchall()
        if len(rows) != 1:
            raise RuntimeError("synthetic selected story fixture missing")
        facts = observe(kwargs.get("messages") or [], rows[0][0])
        name = (kwargs.get("response_format") or {}).get("json_schema", {}).get("name", "")
        facts["stage"] = name if name in ("InterviewStrategy", "InterviewQuestion") else "other"
        fd = os.open(state / "observer.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a") as out:
            out.write(json.dumps(facts) + "\n")
        return original(client, **kwargs)

    fixtures.FixtureChatClient.create_chat_completion = observed
    seed = story._seed

    def seed_verified(session_factory, state, count):
        from src.auth_repository import AccountRepository
        seed(session_factory, state, count)
        accounts = json.loads((state / "accounts.json").read_text())
        repository = AccountRepository(session_factory)
        for account in accounts.values():
            repository.mark_email_verified(account["id"])

    story._seed = seed_verified
    return story.serve(args)


def run(args: argparse.Namespace) -> int:
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
                subprocess.run(["npm", "run", "build"], cwd=frontend, env=env, check=True)
                with (state / "web.log").open("w") as web_log:
                    web = subprocess.Popen(["npx", "next", "start", "-p", str(args.web_port)], cwd=frontend, env=env, stdout=web_log, stderr=subprocess.STDOUT, start_new_session=True)
                    stack._wait(f"http://localhost:{args.web_port}/", 60, "web")
                    pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", STORY_API_URL=f"http://localhost:{args.api_port}/api/v1",
                                  STORY_ACCOUNTS_FILE=str(state / "accounts.json"), STORY_OUTPUT_DIR=str(state / "playwright-results"))
                    result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.data-export-connected.config.ts", "--reporter=json"], cwd=frontend, env=pw_env, capture_output=True)
                    if result.returncode:
                        # Emit only numeric source locations from the structured reporter; never raw error text.
                        try:
                            report = json.loads(result.stdout)
                            def failed_locations(node):
                                if isinstance(node, dict):
                                    for error in node.get("errors", []):
                                        loc = error.get("location") or {}
                                        if str(loc.get("file", "")).endswith("export.spec.ts") and isinstance(loc.get("line"), int):
                                            print(f"Synthetic browser failure at export.spec.ts:{loc['line']}")
                                    for value in node.values():
                                        failed_locations(value)
                                elif isinstance(node, list):
                                    for value in node:
                                        failed_locations(value)
                            failed_locations(report)
                        except (ValueError, TypeError):
                            pass
                        print("Story Practice connected: FAIL (raw browser output withheld for privacy)")
                        return result.returncode
                    observations = [json.loads(line) for line in (state / "observer.jsonl").read_text().splitlines()]
                    if not observations or not any(qualifies(x) for x in observations):
                        raise AssertionError("selected story context was not observed at the model boundary")
                    if any(x["unselected"] or x["foreign"] for x in observations):
                        raise AssertionError("unselected or foreign story context reached the model boundary")
                    ids = json.loads((state / "accounts.json").read_text())
                    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
                        rows = db.execute("SELECT id, user_id, status, evidence_state FROM candidate_stories ORDER BY id").fetchall()
                        uses = db.execute("SELECT user_id, story_id, session_id FROM story_uses").fetchall()
                        sessions = db.execute("SELECT session_id, user_id FROM interview_sessions").fetchall()
                    if len(rows) != 3 or [r[1] for r in rows] != [ids["owner"]["id"], ids["owner"]["id"], ids["other"]["id"]]:
                        raise AssertionError("story ownership state invalid")
                    if any(r[2:] != ("user_created", "none") for r in rows):
                        raise AssertionError("story provenance state changed")
                    if len(sessions) != 1 or sessions[0][1] != ids["owner"]["id"] or uses != [(ids["owner"]["id"], rows[0][0], sessions[0][0])]:
                        raise AssertionError("story use attribution or session state invalid")
                    print(f"Candidate export connected: 1 PASS; bounded model observations={len(observations)}; stages={sorted({x['stage'] for x in observations})}; disposable attribution PASS")
                    return 0
        finally:
            stack._stop_owned_process_group(web)
            stack._stop(api)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18448)
    p.add_argument("--web-port", type=int, default=13448)
    p.add_argument("--state-dir")
    args = p.parse_args()
    if args.mode == "serve":
        state = Path(args.state_dir).resolve() if args.state_dir else None
        if (not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not state.name.startswith("ask4mo_story_connected_") or not state.is_dir() or (state / "journey.db").exists()):
            raise SystemExit("serve requires a fresh disposable story directory")
        return serve(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
