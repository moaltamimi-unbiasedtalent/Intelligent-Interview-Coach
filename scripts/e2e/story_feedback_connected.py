#!/usr/bin/env python3
"""Private synthetic Story Bank to Practice qualification; loopback only."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import platform
import re
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


def observe(messages, story_id: int, stage: str) -> dict:
    """Retain only bounded facts from the synthetic model boundary."""
    fixture = json.loads((ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
    question, answer = fixture["questions"][0], fixture["answer"]
    user = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "user")
    all_text = "\n".join(str(m.get("content", "")) for m in messages)
    start, end = "<<<UNTRUSTED_REFERENCE_DATA>>>", "<<<END_UNTRUSTED_REFERENCE_DATA>>>"
    wrapped = user.count(start) == 1 and user.count(end) == 1 and user.index(start) < user.index(end)
    reference = user.split(start, 1)[1].split(end, 1)[0] if wrapped else ""
    def section(label):
        match = re.search(r"(?ms)^\[" + label + r"\]\n(.*?)(?=\n\n\[[a-z_]+\]\n|\Z)", reference)
        return match.group(1) if match else ""
    background = section("candidate_background")
    opening, closing = f"[[STORY {story_id} BEGIN]]", f"[[STORY {story_id} END]]"
    identity = opening in background and closing in background and background.index(opening) < background.index(closing)
    block = background.split(opening, 1)[1].split(closing, 1)[0] if identity else ""
    return {"stage": stage, "selected": SELECTED in block,
            "identity": identity,
            "unverified": "verification: unverified" in block,
            "candidate_account": "the candidate's own account" in block,
            "unselected": UNSELECTED in all_text, "foreign": FOREIGN in all_text,
            "question": section("interview_question").strip() == question,
            "answer": section("candidate_answer").strip() == answer,
            "reference_wrapped": wrapped and "untrusted reference data" in user.lower() and "not as instructions" in user.lower(),
            "separate": all(marker not in question and marker not in answer for marker in (SELECTED, UNSELECTED, FOREIGN, "[[STORY"))}


def qualifies(observations: list[dict]) -> bool:
    evaluations = [f for f in observations if f["stage"] == "AnswerEvaluation"]
    if len(evaluations) != 1:
        return False
    f = evaluations[0]
    return all(f[k] for k in ("selected", "identity", "unverified", "candidate_account", "question", "answer", "reference_wrapped", "separate")) and not any(f[k] for k in ("unselected", "foreign"))


def serve(args: argparse.Namespace) -> int:
    state = Path(args.state_dir)
    from scripts.e2e import journey_fakes as fixtures
    original = fixtures.FixtureChatClient.create_chat_completion

    def observed(client, **kwargs):
        with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
            rows = db.execute("SELECT id FROM candidate_stories WHERE title = ?", ("Selected synthetic story",)).fetchall()
        if len(rows) != 1:
            raise RuntimeError("synthetic selected story fixture missing")
        name = (kwargs.get("response_format") or {}).get("json_schema", {}).get("name", "")
        stage = name if name in ("InterviewStrategy", "InterviewQuestion", "AnswerEvaluation") else "other"
        facts = observe(kwargs.get("messages") or [], rows[0][0], stage)
        fd = os.open(state / "observer.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a") as out:
            out.write(json.dumps(facts) + "\n")
        return original(client, **kwargs)

    fixtures.FixtureChatClient.create_chat_completion = observed
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
                    result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.story-feedback-connected.config.ts", "--reporter=json"], cwd=frontend, env=pw_env, capture_output=True)
                    if result.returncode:
                        # Emit only numeric source locations from the structured reporter; never raw error text.
                        try:
                            report = json.loads(result.stdout)
                            def failed_locations(node):
                                if isinstance(node, dict):
                                    for error in node.get("errors", []):
                                        loc = error.get("location") or {}
                                        if str(loc.get("file", "")).endswith("feedback.spec.ts") and isinstance(loc.get("line"), int):
                                            print(f"Synthetic browser failure at feedback.spec.ts:{loc['line']}")
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
                    stages = Counter(x["stage"] for x in observations)
                    if stages != {"InterviewStrategy": 1, "InterviewQuestion": 1, "AnswerEvaluation": 1}:
                        raise AssertionError("unexpected offline model-call counts")
                    if not qualifies(observations):
                        raise AssertionError("selected story context was not observed at the model boundary")
                    if any(x["unselected"] or x["foreign"] for x in observations):
                        raise AssertionError("unselected or foreign story context reached the model boundary")
                    ids = json.loads((state / "accounts.json").read_text())
                    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
                        rows = db.execute("SELECT id, user_id, status, evidence_state FROM candidate_stories ORDER BY id").fetchall()
                        uses = db.execute("SELECT user_id, story_id, session_id FROM story_uses").fetchall()
                        sessions = db.execute("SELECT session_id, user_id, state_payload FROM interview_sessions").fetchall()
                    if len(rows) != 3 or [r[1] for r in rows] != [ids["owner"]["id"], ids["owner"]["id"], ids["other"]["id"]]:
                        raise AssertionError("story ownership state invalid")
                    if any(r[2:] != ("user_created", "none") for r in rows):
                        raise AssertionError("story provenance state changed")
                    if len(sessions) != 1 or sessions[0][1] != ids["owner"]["id"] or uses != [(ids["owner"]["id"], rows[0][0], sessions[0][0])]:
                        raise AssertionError("story use attribution or session state invalid")
                    payload = json.loads(sessions[0][2])
                    fixture = json.loads((ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
                    evaluations = payload.get("evaluations", [])
                    if payload.get("answers") != [fixture["answer"]] or len(evaluations) != 1:
                        raise AssertionError("one matching persisted answer and evaluation required")
                    if any(evaluations[0].get(key) != value for key, value in fixture["evaluation"].items()):
                        raise AssertionError("persisted evaluation does not match the synthetic fixture")
                    print(f"Story feedback connected: 1 PASS; bounded model observations={len(observations)}; stage_counts={dict(sorted(stages.items()))}; disposable attribution PASS")
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
