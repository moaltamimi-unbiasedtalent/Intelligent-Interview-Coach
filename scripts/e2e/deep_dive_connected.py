#!/usr/bin/env python3
"""English Deep Dive on real disposable services; only model replies are synthetic."""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.e2e import journey_stack as stack  # noqa: E402
from scripts.e2e import story_bank_connected as story  # noqa: E402

BRANCH_QUESTION = "Which synthetic decision trade-off did you make?"
MAIN_ANSWER = "Synthetic main answer with distinct detail"
BRANCH_ANSWER = "Synthetic deep dive answer with distinct detail"
OBSERVATION_LIMIT = 16
STAGES = ("InterviewStrategy", "InterviewQuestion", "BranchQuestion", "AnswerEvaluation", "FinalInterviewReport")
_LOCK = threading.Lock()
FACTS = {
    "create": {"main_answer": True, "branch_question": True, "branch_evaluation": True,
               "return_without_reload": True, "original_evaluation": True, "main_counter_unchanged": True,
               "report_saved": True, "pre_evaluation": 422, "foreign_active": 422, "foreign_deep_dive": 422,
               "foreign_refusal_safe": True, "foreign_state_unchanged": True, "console_errors": 0, "page_errors": 0},
    "read": {"branch_parent_link": True, "branch_identity": True, "fresh_auth": True, "read_only": True,
             "foreign_refusal_safe": True, "foreign_history": 404, "console_errors": 0, "page_errors": 0},
}


def valid_facts(value, phase):
    expected = FACTS.get(phase)
    return (expected is not None and isinstance(value, dict) and set(value) == set(expected)
            and all(type(value[k]) is type(v) and value[k] == v for k, v in expected.items()))


def load_facts(path, phase):
    try:
        if path.stat().st_size > 2048:
            raise ValueError
        value = json.loads(path.read_text())
        if not valid_facts(value, phase):
            raise ValueError
        return value
    except (OSError, ValueError, TypeError):
        raise ValueError("bounded browser evidence invalid") from None


def phase_ok(result):
    if result.returncode:
        return False
    try:
        value = json.loads(result.stdout)
        stats = value["stats"]
        return (not value.get("errors", []) and type(stats["expected"]) is int and stats["expected"] == 1
                and type(stats["unexpected"]) is int and stats["unexpected"] == 0
                and type(stats["skipped"]) is int and stats["skipped"] == 0)
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def record(state, stage, report_branch_evidence=False):
    if stage not in STAGES or type(report_branch_evidence) is not bool or (report_branch_evidence and stage != "FinalInterviewReport"):
        raise ValueError("unapproved observation")
    target = state / "model-stages.jsonl"
    with _LOCK:
        if target.exists() and (target.stat().st_size > 2048 or len(target.read_text().splitlines()) >= OBSERVATION_LIMIT):
            raise ValueError("bounded observation limit exceeded")
        fd = os.open(target, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(json.dumps({"stage": stage, "report_branch_evidence": report_branch_evidence}) + "\n")


def serve(args):
    import tests.conftest  # noqa: F401 (isolate before application imports)
    from scripts.e2e import journey_fakes as fixtures

    state = Path(args.state_dir)
    original = fixtures.FixtureChatClient.create_chat_completion

    def observed(client, **kwargs):
        stage = (kwargs.get("response_format") or {}).get("json_schema", {}).get("name", "")
        report_evidence = False
        if stage == "FinalInterviewReport":
            # Inspect transient synthetic input at the actual model boundary. Never retain prompts.
            marker = "Deep dive: deepen reasoning, level 1: score 81/100"
            report_evidence = any(marker in str(message.get("content", "")) for message in kwargs.get("messages", []))
        record(state, stage, report_evidence)
        result = original(client, **kwargs)
        if stage == "BranchQuestion":
            payload = json.loads(result.content)
            payload.update(question=BRANCH_QUESTION, focus_area="Synthetic judgement")
            result = dataclasses.replace(result, content=json.dumps(payload))
        if stage == "AnswerEvaluation" and client.calls.count("AnswerEvaluation") == 2:
            payload = json.loads(result.content)
            payload.update(overall_score=81, strengths=["Synthetic branch reasoning made explicit"])
            result = dataclasses.replace(result, content=json.dumps(payload))
        return result

    fixtures.FixtureChatClient.create_chat_completion = observed
    return story.serve(args)


def snapshot(state):
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in ("interviews", "questions", "answers", "reports", "interview_sessions")}


def database_facts(state):
    """Project only fixed boolean observations; no candidate text, session IDs or database dumps."""
    try:
        identity = json.loads((state / "deep-dive-private.json").read_text())
        owner = json.loads((state / "accounts.json").read_text())["owner"]["id"]
        with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
            interviews = db.execute("SELECT id,user_id,source_session_id FROM interviews").fetchall()
            questions = db.execute("SELECT position,canonical_question,is_deep_dive,parent_position FROM questions ORDER BY position").fetchall()
            answers = db.execute("SELECT a.text,a.evaluation FROM answers a JOIN questions q ON q.id=a.question_id ORDER BY q.position").fetchall()
            reports = db.execute("SELECT interview_id FROM reports").fetchall()
            sessions = db.execute("SELECT user_id,state_payload FROM interview_sessions").fetchall()
        fixture = json.loads((ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
        counts = len(interviews) == 1 and len(questions) == 2 and len(answers) == 2 and len(reports) == 1 and len(sessions) == 1
        main = next((q for q in questions if not q[2]), None)
        branch = next((q for q in questions if q[2]), None)
        payload = json.loads(sessions[0][1]) if len(sessions) == 1 else {}
        archived = payload.get("branches", [])
        return {
            "single_session_branch_report": counts,
            "owner_source_identity": interviews == [(identity["history_id"], owner, identity["session_id"])] and len(sessions) == 1 and sessions[0][0] == owner,
            "exact_saved_questions": bool(main and branch and main[1] == fixture["questions"][0] and branch[1] == BRANCH_QUESTION),
            "branch_parent_matches_main_position": bool(main and branch and branch[3] == main[0]),
            "exact_saved_answers_evaluations": len(answers) == 2 and [a[0] for a in answers] == [MAIN_ANSWER, BRANCH_ANSWER] and [json.loads(a[1]) for a in answers] == [fixture["evaluation"], dict(fixture["evaluation"], overall_score=81, strengths=["Synthetic branch reasoning made explicit"])],
            "durable_branch_identity": len(archived) == 1 and len(archived[0].get("questions", [])) == 1 and archived[0]["questions"][0]["branch_id"] == identity["branch_id"] and archived[0]["parent_question_id"] == identity["parent_question_id"],
            "single_report_identity": reports == [(identity["history_id"],)],
        }
    except (OSError, ValueError, KeyError, TypeError, IndexError, sqlite3.Error):
        return {}


def parent_link_observation(state):
    try:
        with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
            main = db.execute("SELECT position FROM questions WHERE is_deep_dive=0 ORDER BY position").fetchall()
            branch = db.execute("SELECT position,parent_position FROM questions WHERE is_deep_dive=1 ORDER BY position").fetchall()
        if len(main) == 1 and len(branch) == 1 and all(type(v) is int and 0 <= v <= 100 for v in (*main[0], *branch[0])):
            return {"main_position": main[0][0], "branch_position": branch[0][0], "branch_parent_position": branch[0][1]}
    except sqlite3.Error:
        pass
    return {}


def safe_failure(result):
    """Retain only fixed classifications and test-source line numbers, never raw errors."""
    output = {"classification": "browser_assertion_or_execution_failed"}
    try:
        value = json.loads(result.stdout)
        output["counts"] = {k: value["stats"].get(k) if type(value["stats"].get(k)) is int else None for k in ("expected", "unexpected", "skipped")}
        lines = []
        def locate(node):
            if isinstance(node, dict):
                loc = node.get("location") or {}
                if str(loc.get("file", "")).endswith("deep-dive.spec.ts") and type(loc.get("line")) is int:
                    lines.append(loc["line"])
                for v in node.values():
                    locate(v)
            elif isinstance(node, list):
                for v in node:
                    locate(v)
        locate(value)
        output["source_lines"] = sorted(set(lines))[:10]
    except (ValueError, TypeError, KeyError):
        output["classification"] = "browser_report_unreadable"
    return output


def run(args):
    stack._check_ports(args.api_port, args.web_port)
    state = Path(tempfile.mkdtemp(prefix="ask4mo_story_connected_"))
    evidence = Path(tempfile.mkdtemp(prefix="ask4mo_deep_dive_evidence_"))
    api = web = None
    stage = "setup"
    code = 1
    summary = {"scope": "ENGLISH — DISPOSABLE CONNECTED STACK — SYNTHETIC OFFLINE MODEL",
               "result": "FAIL", "language_qualified": False, "production_gate_approval": False}
    try:
        font = state / "font.cjs"
        font.write_text("module.exports = new Proxy({}, {get: () => `/* latin */\\n@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; src: url(mock.woff2) format('woff2'); }`});\n")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(state), "TMPDIR": tempfile.gettempdir(),
               "PYTHON_DOTENV_DISABLED": "1", "ASK4MO_PROVIDER_MODE": "offline", "NEXT_TELEMETRY_DISABLED": "1",
               "NEXT_FONT_GOOGLE_MOCKED_RESPONSES": str(font), "NEXT_DIST_DIR": ".next",
               "NEXT_PUBLIC_API_BASE_URL": f"http://localhost:{args.api_port}/api/v1"}
        cache = Path.home() / ("Library/Caches/ms-playwright" if platform.system() == "Darwin" else ".cache/ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(cache))
        stage = "api_readiness"
        with (state / "api.log").open("w") as api_log, (state / "web.log").open("w") as web_log:
            api = subprocess.Popen([sys.executable, str(Path(__file__)), "serve", "--state-dir", str(state), "--api-port", str(args.api_port), "--web-port", str(args.web_port)], cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT)
            stack._wait(f"http://127.0.0.1:{args.api_port}/api/v1/health", 90, "API")
            stage = "web_build"
            build = subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", env=env, capture_output=True)
            if build.returncode:
                raise RuntimeError("isolated frontend build failed")
            stage = "web_readiness"
            web = subprocess.Popen(["npx", "next", "start", "-p", str(args.web_port)], cwd=ROOT / "frontend", env=env, stdout=web_log, stderr=subprocess.STDOUT, start_new_session=True)
            stack._wait(f"http://localhost:{args.web_port}/", 60, "web")
            pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", STORY_API_URL=f"http://localhost:{args.api_port}/api/v1", STORY_ACCOUNTS_FILE=str(state / "accounts.json"), DEEP_DIVE_STATE_DIR=str(state))
            facts = {}
            before = calls_before = None
            for phase in ("create", "read"):
                stage = "connected_browser_" + phase
                result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.deep-dive-connected.config.ts", "--reporter=json"], cwd=ROOT / "frontend", env=dict(pw_env, DEEP_DIVE_PHASE=phase), capture_output=True)
                if not phase_ok(result):
                    summary["browser_failure"] = safe_failure(result)
                    summary["persisted_observations"] = database_facts(state)
                    summary["parent_link_observation"] = parent_link_observation(state)
                    if phase == "read":
                        summary["read_changed_persistence"] = snapshot(state) != before
                        summary["read_replayed_model"] = (state / "model-stages.jsonl").read_bytes() != calls_before
                    raise RuntimeError("connected browser qualification failed")
                facts[phase] = load_facts(state / f"{phase}-facts.json", phase)
                summary["browser_facts"] = dict(facts)
                if phase == "create":
                    before = snapshot(state)
                    calls_before = (state / "model-stages.jsonl").read_bytes()
            stage = "evidence_verification"
            calls = [json.loads(line) for line in (state / "model-stages.jsonl").read_text().splitlines()]
            expected = ["InterviewStrategy", "InterviewQuestion", "AnswerEvaluation", "BranchQuestion", "AnswerEvaluation", "FinalInterviewReport"]
            if [x["stage"] for x in calls] != expected or not calls[-1]["report_branch_evidence"]:
                raise RuntimeError("model or report boundary evidence invalid")
            if snapshot(state) != before or (state / "model-stages.jsonl").read_bytes() != calls_before:
                raise RuntimeError("History reads changed records or replayed model execution")
            db = database_facts(state)
            if not db or not all(db.values()):
                raise RuntimeError("durable identity evidence invalid")
            summary.update(result="PASS", browser_scenarios=1, browser_phases=2, browser_facts=facts,
                           persisted_observations=db, model_calls=len(calls), report_branch_evidence=True,
                           monetary_cost="UNKNOWN: fixture reports no cost")
            code = 0
    except (Exception, SystemExit):
        summary["failure_stage"] = stage
        code = 1
    finally:
        cleanup_ok = False
        try:
            stack._stop_owned_process_group(web)
            stack._stop(api)
            if api is not None:
                api.wait(timeout=10)
            cleanup_ok = all(proc is None or proc.poll() is not None for proc in (api, web))
        except (OSError, subprocess.TimeoutExpired):
            cleanup_ok = False
        summary["owned_process_cleanup"] = "PASS" if cleanup_ok else "FAIL"
        if not cleanup_ok:
            summary.update(result="FAIL", failure_stage="owned_process_cleanup")
            code = 1
        observations = state / "model-stages.jsonl"
        if observations.exists() and observations.stat().st_size <= 2048:
            calls = [json.loads(line) for line in observations.read_text().splitlines()]
            summary["model_stages"] = [x["stage"] for x in calls]
            summary["report_branch_evidence"] = any(x["report_branch_evidence"] for x in calls)
        summary["source_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        # Keep only sanitized results after deleting this operation's synthetic stores/logs.
        if cleanup_ok:
            shutil.rmtree(state)
        out = evidence / "summary.json"
        out.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
        out.chmod(0o600)
        print(json.dumps(summary, sort_keys=True))
        print(f"Sanitized evidence: {out}")
    return code



def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("run", "serve"))
    p.add_argument("--api-port", type=int, default=18480)
    p.add_argument("--web-port", type=int, default=13480)
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
