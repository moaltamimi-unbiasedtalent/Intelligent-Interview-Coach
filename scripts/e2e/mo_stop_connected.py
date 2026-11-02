#!/usr/bin/env python3
"""One English, synthetic UI-to-real-SSE Stop journey; no external services."""
from __future__ import annotations

import argparse
import json
import os
import platform
import select
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

LATE_ANSWER = "Synthetic late fixture completion"
_OBSERVATION_LOCK = threading.Lock()
OBSERVATION_LIMIT = 16
FACTS = {
    "start_requests": 1, "cancel_requests": 1, "run_identity_same": True,
    "progress_visible": True, "real_progress_observed": True, "real_stopping_observed": True, "real_terminal_observed": True, "foreign_cancel_status": 404, "foreign_read_status": 404,
    "foreign_events_status": 404, "foreign_refusal_safe": True, "other_authenticated": True,
    "stop_recorded": True, "stopping_visible": True, "terminal_cancelled": True,
    "late_answer_hidden": True, "revisit_same_run": True, "revisit_start_requests": 0,
    "console_errors": 0, "page_errors": 0, "cancel_pending_true": True,
    "foreign_state_unchanged": True, "terminal_settled": True, "late_tool_absent": True,
}


def valid_facts(value):
    return (isinstance(value, dict) and set(value) == set(FACTS)
            and all(type(value[k]) is type(v) and value[k] == v for k, v in FACTS.items()))


def phase_ok(result):
    if result.returncode:
        return False
    try:
        report = json.loads(result.stdout)
        stats = report["stats"]
        return (not report.get("errors", []) and type(stats["expected"]) is int and stats["expected"] == 1
                and type(stats["unexpected"]) is int and stats["unexpected"] == 0
                and type(stats["skipped"]) is int and stats["skipped"] == 0)
    except (ValueError, KeyError, TypeError):
        return False


def record(state, kind):
    if kind not in ("model_entered", "model_returned", "tool_dispatch_attempt"):
        raise ValueError("unapproved observation")
    target = state / "calls.jsonl"
    with _OBSERVATION_LOCK:
        if target.exists() and (target.stat().st_size > 2048 or len(target.read_text().splitlines()) >= OBSERVATION_LIMIT):
            raise ValueError("bounded observation limit exceeded")
        fd = os.open(target, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(json.dumps({"kind": kind}) + "\n")


class ControlledModel:
    """Only model replies are synthetic; the graph and all application controls are real."""
    def __init__(self, variant="healthy", fixtures=None, *, state=None, hold=True):
        self.state = state
        self.hold = hold
        self.calls = 0

    def bind_tools(self, schemas):
        return self

    def invoke(self, messages):
        from langchain_core.messages import AIMessage

        self.calls += 1
        if self.state:
            record(self.state, "model_entered")
        if self.hold and self.calls == 1:
            fd = os.open(self.state / "barrier-release", os.O_RDONLY | os.O_NONBLOCK)
            try:
                target = self.state / "barrier-entered.json"
                with target.open("x") as out:
                    out.write('{"entered":true}')
                target.chmod(0o600)
                if not select.select([fd], [], [], 60)[0] or not os.read(fd, 32):
                    raise RuntimeError("private fixture barrier was not released")
            finally:
                os.close(fd)
        if self.state:
            record(self.state, "model_returned")
        return AIMessage(content=LATE_ANSWER,
                         tool_calls=[{"id": "synthetic-late-tool", "name": "GenerateInterviewQuestions", "args": {"role": "Nurse"}}] if self.calls == 1 else [],
                         usage_metadata={"input_tokens": 5, "output_tokens": 4, "total_tokens": 9})


def serve(args):
    import tests.conftest  # noqa: F401  (isolate before importing application modules)
    from scripts.e2e import journey_fakes as fixtures
    from src.agent.registry import ToolRegistry

    state = Path(args.state_dir)
    original = ToolRegistry.validate_and_run

    def observed(registry, *positional, **kwargs):
        record(state, "tool_dispatch_attempt")
        return original(registry, *positional, **kwargs)

    ToolRegistry.validate_and_run = observed
    fixtures.ScriptedAgentModel = lambda variant="healthy", fixtures=None: ControlledModel(variant, fixtures, state=state)
    return story.serve(args)


def verify_database(state):
    run_id = json.loads((state / "run-id.json").read_text())["run_id"]
    owner = json.loads((state / "accounts.json").read_text())["owner"]["id"]
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT run_id,owner_user_id,status,settled FROM agent_run_controls").fetchall()
        if rows != [(run_id, owner, "cancelled", 1)]:
            return False
        # The real checkpoint run index must still identify exactly this owner/run.
        if db.execute("SELECT count(*) FROM preparation_runs WHERE run_id=? AND owner_user_id=?", (run_id, owner)).fetchone()[0] != 1:
            return False
        usage = db.execute("SELECT user_id,model_calls,input_tokens,output_tokens,total_tokens,cost_usd_micros,cost_source FROM ai_usage_facts WHERE usage_key=?", ("agent:" + run_id,)).fetchall()
        if usage != [(owner, 1, 5, 4, 9, None, "unavailable")]:
            return False
    return True


def run(args):
    stack._check_ports(args.api_port, args.web_port)
    state = Path(tempfile.mkdtemp(prefix="ask4mo_story_connected_"))
    evidence = Path(tempfile.mkdtemp(prefix="ask4mo_mo_stop_evidence_"))
    api = web = None
    stage = "setup"
    code = 1
    summary = {"scope": "ENGLISH — DISPOSABLE CONNECTED STACK — SYNTHETIC OFFLINE MODEL",
               "result": "FAIL", "language_qualified": False, "production_gate_approval": False}
    try:
        os.mkfifo(state / "barrier-release", 0o600)
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
            stage = "connected_browser"
            result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.mo-stop-connected.config.ts", "--reporter=json"], cwd=ROOT / "frontend", env=dict(env, BASE_URL=f"http://localhost:{args.web_port}", STORY_API_URL=f"http://localhost:{args.api_port}/api/v1", STORY_ACCOUNTS_FILE=str(state / "accounts.json"), MO_STOP_STATE_DIR=str(state)), capture_output=True)
            if not phase_ok(result):
                # Preserve safe locations/counts, never arbitrary browser errors or raw payloads.
                try:
                    value = json.loads(result.stdout)
                    summary["browser_counts"] = {k: value["stats"].get(k) for k in ("expected", "unexpected", "skipped")}
                    lines = []
                    def locate(node):
                        if isinstance(node, dict):
                            loc = node.get("location") or {}
                            if str(loc.get("file", "")).endswith("stop.spec.ts") and type(loc.get("line")) is int:
                                lines.append(loc["line"])
                            for v in node.values():
                                locate(v)
                        elif isinstance(node, list):
                            for v in node:
                                locate(v)
                    locate(value)
                    summary["browser_failure_lines"] = sorted(set(lines))[:10]
                except (ValueError, TypeError, KeyError):
                    summary["browser_report"] = "unreadable"
                raise RuntimeError("connected browser qualification failed")
            stage = "evidence_verification"
            facts_path = state / "browser-facts.json"
            if not facts_path.is_file() or facts_path.stat().st_size > 2048:
                raise RuntimeError("bounded browser evidence missing")
            facts = json.loads(facts_path.read_text())
            if not valid_facts(facts):
                raise RuntimeError("bounded browser evidence invalid")
            calls = [json.loads(x)["kind"] for x in (state / "calls.jsonl").read_text().splitlines()]
            if calls != ["model_entered", "model_returned"] or not verify_database(state):
                raise RuntimeError("durable state or no-replay evidence invalid")
            summary.update(result="PASS", browser_scenarios=1, browser_facts=facts, model_calls=1, tool_dispatch_attempts=0,
                           durable_cancelled=True, durable_settled=True, duplicate_runs=0,
                           fixture_tokens={"input": 5, "output": 4, "total": 9}, monetary_cost="UNKNOWN: fixture reports no cost")
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
    p.add_argument("--api-port", type=int, default=18479)
    p.add_argument("--web-port", type=int, default=13479)
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
