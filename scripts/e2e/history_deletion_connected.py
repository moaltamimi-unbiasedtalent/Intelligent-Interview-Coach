#!/usr/bin/env python3
"""Selective completed-interview deletion on real disposable services, synthetic identities only."""
from __future__ import annotations

import argparse
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
from scripts.e2e.deep_dive_connected import phase_ok  # noqa: E402

OBSERVATION_LIMIT = 16
STAGES = ("InterviewStrategy", "InterviewQuestion", "AnswerEvaluation", "FinalInterviewReport")
_LOCK = threading.Lock()
FACTS = {
    "prepare": {"records": 3, "owners": 2, "completed": True, "distinct_identities": True},
    "refuse": {"foreign_status": 404, "anonymous_status": 401, "cancel_zero_delete": True,
               "selected_identity": True, "warning_visible": True, "cancel_default_focus": True,
               "foreign_refusal_safe": True},
    "delete": {"owner_status": 200, "delete_requests": 1, "target_removed": True,
               "owner_keeper_preserved": True, "foreign_keeper_preserved": True,
               "history_missing": 404, "repeat_delete": 404, "source_read": 422, "source_report": 422,
               "fresh_auth_absent": True, "no_model_replay": True, "foreign_refusal_safe": True,
               "console_errors": 0, "page_errors": 0},
}
ROLES = ("Synthetic Deletion Target", "Synthetic Owner Keeper", "Synthetic Foreign Keeper")
ANSWERS = ("Synthetic target answer", "Synthetic owner keeper answer", "Synthetic foreign keeper answer")


def fixture_text_canaries(value):
    """Known synthetic content, excluding numeric scores and short schema identifiers."""
    if isinstance(value, str):
        return [value] if len(value) >= 16 else []
    if isinstance(value, dict):
        return [text for item in value.values() for text in fixture_text_canaries(item)]
    if isinstance(value, list):
        return [text for item in value for text in fixture_text_canaries(item)]
    return []


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


def record(state, stage):
    if stage not in STAGES:
        raise ValueError("unapproved observation")
    target = state / "model-stages.jsonl"
    line = json.dumps({"stage": stage}) + "\n"
    with _LOCK:
        if target.exists() and (target.stat().st_size + len(line.encode()) > 2048 or len(target.read_text().splitlines()) >= OBSERVATION_LIMIT):
            raise ValueError("bounded observation limit exceeded")
        fd = os.open(target, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(line)


def serve(args):
    import tests.conftest  # noqa: F401 (isolate before application imports)
    from scripts.e2e import journey_fakes as fixtures

    state = Path(args.state_dir)
    original = fixtures.FixtureChatClient.create_chat_completion

    def observed(client, **kwargs):
        stage = (kwargs.get("response_format") or {}).get("json_schema", {}).get("name", "")
        record(state, stage)
        return original(client, **kwargs)

    fixtures.FixtureChatClient.create_chat_completion = observed
    return story.serve(args)


def snapshot(state):
    """Read only this harness's synthetic DB. Raw rows never leave the process."""
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        result = {table: [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                  for table in ("interviews", "questions", "answers", "reports", "interview_sessions")}
        result["deletion_audit"] = [dict(row) for row in db.execute("SELECT * FROM audit_events WHERE event_type='interview.deleted' ORDER BY id")]
        return result


def verify_prepared(state, data):
    try:
        identity = json.loads((state / "history-delete-private.json").read_text())
        accounts = json.loads((state / "accounts.json").read_text())
        fixture = json.loads((ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
        ids, sessions = identity["ids"], identity["sessions"]
        if len(ids) != 3 or len(set(ids)) != 3 or len(sessions) != 3 or len(set(sessions)) != 3:
            return False
        if any(len(data[table]) != 3 for table in ("interviews", "questions", "answers", "reports", "interview_sessions")) or data["deletion_audit"]:
            return False
        for index, iid in enumerate(ids):
            row = next(r for r in data["interviews"] if r["id"] == iid)
            owner = accounts["owner" if index < 2 else "other"]["id"]
            if row["user_id"] != owner or row["source_session_id"] != sessions[index] or json.loads(row["configuration"])["target_role"] != ROLES[index] or row["status"].lower() != "completed":
                return False
            question = next(q for q in data["questions"] if q["interview_id"] == iid)
            answer = next(a for a in data["answers"] if a["question_id"] == question["id"])
            report = next(r for r in data["reports"] if r["interview_id"] == iid)
            session = next(s for s in data["interview_sessions"] if s["session_id"] == sessions[index])
            if question["canonical_question"] != fixture["questions"][0] or answer["text"] != ANSWERS[index] or json.loads(answer["evaluation"]) != fixture["evaluation"] or json.loads(report["report"]) != fixture["report"] or session["user_id"] != owner:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return False


def deletion_facts(before, after, identity, owner):
    """Fixed boolean projection: exact deletion delta, unchanged sentinels and bounded audit."""
    try:
        iid, sid = identity["ids"][0], identity["sessions"][0]
        qids = {q["id"] for q in before["questions"] if q["interview_id"] == iid}
        expected = {
            "interviews": [r for r in before["interviews"] if r["id"] != iid],
            "questions": [r for r in before["questions"] if r["interview_id"] != iid],
            "answers": [r for r in before["answers"] if r["question_id"] not in qids],
            "reports": [r for r in before["reports"] if r["interview_id"] != iid],
            "interview_sessions": [r for r in before["interview_sessions"] if r["session_id"] != sid],
        }
        audit = after["deletion_audit"]
        exact_audit = (not before["deletion_audit"] and len(audit) == 1 and audit[0]["event_type"] == "interview.deleted"
                       and audit[0]["actor_user_id"] == owner and audit[0]["target_type"] == "interview"
                       and audit[0]["target_id"] == str(iid) and audit[0]["result"] == "success")
        # Audit may contain only its existing metadata and empty optional context.
        fixture = json.loads((ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
        private_text = (*ROLES, *ANSWERS, story.PASSWORD, *(email for email, _ in story.ACCOUNTS.values()),
                        *fixture_text_canaries(fixture))
        context = audit[0]["context"] if exact_audit else None
        if isinstance(context, str):
            context = json.loads(context)
        audit_safe = bool(exact_audit and context in (None, {}) and not any(v in json.dumps(audit) for v in private_text))
        return {"target_interview_removed": after["interviews"] == expected["interviews"],
                "selected_questions_removed": bool(qids) and after["questions"] == expected["questions"],
                "selected_answers_removed": after["answers"] == expected["answers"],
                "selected_report_removed": after["reports"] == expected["reports"],
                "source_session_discarded": after["interview_sessions"] == expected["interview_sessions"],
                "exactly_two_sentinel_records_preserved": len(after["interviews"]) == 2 and all(after[k] == v for k, v in expected.items()),
                "one_owner_attributed_deletion_audit": bool(exact_audit), "audit_metadata_only": audit_safe}
    except (KeyError, IndexError, TypeError, ValueError):
        return {}


def safe_failure(result):
    """Retain only fixed classifications and source lines, never raw browser errors."""
    output = {"classification": "browser_assertion_or_execution_failed"}
    try:
        value = json.loads(result.stdout)
        output["counts"] = {k: value["stats"].get(k) if type(value["stats"].get(k)) is int else None for k in ("expected", "unexpected", "skipped")}
        lines = []
        def locate(node):
            if isinstance(node, dict):
                loc = node.get("location") or {}
                if str(loc.get("file", "")).endswith("deletion.spec.ts") and type(loc.get("line")) is int:
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
    state = Path(tempfile.mkdtemp(prefix="ask4mo_history_delete_connected_"))
    evidence = Path(tempfile.mkdtemp(prefix="ask4mo_history_delete_evidence_"))
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
            pw_env = dict(env, BASE_URL=f"http://localhost:{args.web_port}", STORY_API_URL=f"http://localhost:{args.api_port}/api/v1", STORY_ACCOUNTS_FILE=str(state / "accounts.json"), HISTORY_DELETE_STATE_DIR=str(state))
            facts = {}
            prepared = None
            calls_before = None
            for phase in ("prepare", "refuse", "delete"):
                stage = "connected_browser_" + phase
                result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.history-deletion-connected.config.ts", "--reporter=json"], cwd=ROOT / "frontend", env=dict(pw_env, HISTORY_DELETE_PHASE=phase), capture_output=True)
                if not phase_ok(result):
                    summary["browser_failure"] = safe_failure(result)
                    raise RuntimeError("connected browser qualification failed")
                facts[phase] = load_facts(state / f"{phase}-facts.json", phase)
                summary["browser_facts"] = dict(facts)
                if phase == "prepare":
                    prepared = snapshot(state)
                    if not verify_prepared(state, prepared):
                        raise RuntimeError("prepared record identity invalid")
                    calls_before = (state / "model-stages.jsonl").read_bytes()
                    expected = ["InterviewStrategy", "InterviewQuestion", "AnswerEvaluation", "FinalInterviewReport"] * 3
                    if [json.loads(x)["stage"] for x in calls_before.splitlines()] != expected:
                        raise RuntimeError("unexpected model execution during preparation")
                elif phase == "refuse":
                    if snapshot(state) != prepared or (state / "model-stages.jsonl").read_bytes() != calls_before:
                        raise RuntimeError("refusal or cancellation changed business state or model execution")
                    summary["refusal_and_cancel_state_unchanged"] = True
            stage = "evidence_verification"
            identity = json.loads((state / "history-delete-private.json").read_text())
            owner = json.loads((state / "accounts.json").read_text())["owner"]["id"]
            observations = deletion_facts(prepared, snapshot(state), identity, owner)
            if not observations or not all(observations.values()):
                summary["deletion_observations"] = observations
                raise RuntimeError("deletion persistence or audit evidence invalid")
            if (state / "model-stages.jsonl").read_bytes() != calls_before:
                raise RuntimeError("deletion or reads replayed model execution")
            summary.update(result="PASS", browser_scenarios=1, browser_phases=3, browser_facts=facts,
                           deletion_observations=observations, model_calls=12, no_model_replay=True,
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
    p.add_argument("--api-port", type=int, default=18481)
    p.add_argument("--web-port", type=int, default=13481)
    p.add_argument("--state-dir")
    args = p.parse_args()
    if args.mode == "serve":
        state = Path(args.state_dir).resolve() if args.state_dir else None
        if not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not state.name.startswith("ask4mo_history_delete_connected_") or not state.is_dir() or (state / "journey.db").exists():
            raise SystemExit("fresh disposable test directory required")
        return serve(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
