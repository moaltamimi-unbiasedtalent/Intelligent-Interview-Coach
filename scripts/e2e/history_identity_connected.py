#!/usr/bin/env python3
"""Synthetic owner-scoped completed-History evidence on a disposable local stack."""
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
    from scripts.e2e import journey_fakes as fixtures
    original = fixtures.FixtureChatClient.create_chat_completion
    state = Path(args.state_dir)

    def observed(client, **kwargs):
        schema = (kwargs.get("response_format") or {}).get("json_schema", {}).get("name", "")
        stage = schema if schema in ("InterviewStrategy", "InterviewQuestion", "AnswerEvaluation", "FinalInterviewReport") else "other"
        fd = os.open(state / "model-stages.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a") as out:
            out.write(json.dumps({"stage": stage}) + "\n")
        return original(client, **kwargs)

    fixtures.FixtureChatClient.create_chat_completion = observed
    return story.serve(args)


def snapshot(state):
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in ("interviews", "questions", "answers", "reports")}


def verify_records(state):
    ids = json.loads((state / "history-private.json").read_text())
    accounts = json.loads((state / "accounts.json").read_text())
    fixture = json.loads((ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
    answers = ["Synthetic answer alpha with distinct detail", "Synthetic answer beta with distinct detail"]
    roles = ["Synthetic Owner Role Alpha", "Synthetic Owner Role Beta"]
    with sqlite3.connect(f"file:{state / 'journey.db'}?mode=ro", uri=True) as db:
        if db.execute("SELECT count(*) FROM interviews").fetchone()[0] != 2:
            return False
        for i, name in enumerate(("owner", "other")):
            rows = db.execute("SELECT id,user_id,source_session_id,configuration,status FROM interviews WHERE user_id=? AND source_session_id=?", (accounts[name]["id"], ids["sessions"][i])).fetchall()
            if len(rows) != 1 or rows[0][0] != ids["ids"][i] or json.loads(rows[0][3])["target_role"] != roles[i] or rows[0][4].lower() != "completed":
                return False
            parts = db.execute("SELECT q.canonical_question,a.text,a.evaluation FROM questions q JOIN answers a ON a.question_id=q.id WHERE q.interview_id=?", (ids["ids"][i],)).fetchall()
            if len(parts) != 1 or parts[0][0] != fixture["questions"][0] or parts[0][1] != answers[i] or json.loads(parts[0][2])["overall_score"] != fixture["evaluation"]["overall_score"]:
                return False
            reports = db.execute("SELECT report FROM reports WHERE interview_id=?", (ids["ids"][i],)).fetchall()
            if len(reports) != 1 or json.loads(reports[0][0])["performance_summary"] != fixture["report"]["performance_summary"]:
                return False
    return True


def valid_facts(value):
    expected = {"owners": 2, "foreign": 404, "missing": 404, "anonymous": 401, "read_only": True, "identity": True, "fresh": True}
    return (isinstance(value, dict) and set(value) == set(expected)
            and all(type(value[k]) is type(v) and value[k] == v for k, v in expected.items()))


def phase_ok(result):
    if result.returncode:
        return False
    try:
        stats = json.loads(result.stdout)["stats"]
        return (type(stats["expected"]) is int and stats["expected"] == 1
                and type(stats["unexpected"]) is int and stats["unexpected"] == 0
                and type(stats["skipped"]) is int and stats["skipped"] == 0)
    except (ValueError, KeyError, TypeError):
        return False


def run(args):
    stack._check_ports(args.api_port,args.web_port)
    api=web=None
    with tempfile.TemporaryDirectory(prefix="ask4mo_story_connected_") as tmp:
        state=Path(tmp);font=state/"font.cjs"
        font.write_text("module.exports = new Proxy({}, {get: () => `/* latin */\\n@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; src: url(mock.woff2) format('woff2'); }`});\n")
        env={"PATH":os.environ.get("PATH",""),"HOME":str(state),"TMPDIR":tempfile.gettempdir(),"PYTHON_DOTENV_DISABLED":"1","ASK4MO_PROVIDER_MODE":"offline","NEXT_TELEMETRY_DISABLED":"1","NEXT_FONT_GOOGLE_MOCKED_RESPONSES":str(font),"NEXT_DIST_DIR":".next","NEXT_PUBLIC_API_BASE_URL":f"http://localhost:{args.api_port}/api/v1"}
        cache=Path.home()/("Library/Caches/ms-playwright" if platform.system()=="Darwin" else ".cache/ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"]=os.environ.get("PLAYWRIGHT_BROWSERS_PATH",str(cache));frontend=ROOT/"frontend"
        try:
            with (state/"api.log").open("w") as log, (state/"web.log").open("w") as web_log:
                api=subprocess.Popen([sys.executable,str(Path(__file__)),"serve","--state-dir",str(state),"--api-port",str(args.api_port),"--web-port",str(args.web_port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                stack._wait(f"http://127.0.0.1:{args.api_port}/api/v1/health",90,"API")
                subprocess.run(["npm","run","build"],cwd=frontend,env=env,check=True)
                web=subprocess.Popen(["npx","next","start","-p",str(args.web_port)],cwd=frontend,env=env,stdout=web_log,stderr=subprocess.STDOUT,start_new_session=True)
                stack._wait(f"http://localhost:{args.web_port}/",60,"web")
                pw_env=dict(env,BASE_URL=f"http://localhost:{args.web_port}",STORY_API_URL=f"http://localhost:{args.api_port}/api/v1",STORY_ACCOUNTS_FILE=str(state/"accounts.json"),HISTORY_STATE_DIR=str(state))
                def phase(name):
                    r=subprocess.run(["npx","playwright","test","--config","playwright.history-identity-connected.config.ts","--reporter=json"],cwd=frontend,env=dict(pw_env,HISTORY_PHASE=name),capture_output=True)
                    if not phase_ok(r):
                        try:
                            def locations(node):
                                if isinstance(node,dict):
                                    for error in node.get("errors",[]):
                                        loc=error.get("location") or {}
                                        if str(loc.get("file","")).endswith("history.spec.ts") and isinstance(loc.get("line"),int): print(f"History {name} failure at history.spec.ts:{loc['line']}")
                                    for value in node.values(): locations(value)
                                elif isinstance(node,list):
                                    for value in node: locations(value)
                            locations(json.loads(r.stdout))
                        except (ValueError, TypeError): pass
                        print(f"History {name}: FAIL (raw browser output withheld)")
                        raise RuntimeError("synthetic browser phase failed")
                phase("complete")
                if not verify_records(state): raise RuntimeError("completed History identity evidence failed")
                before=snapshot(state);calls=(state/"model-stages.jsonl").read_text().splitlines()
                if not calls: raise RuntimeError("missing model observation")
                phase("read")
                facts_path=state/"history-facts.json"
                if not facts_path.is_file() or facts_path.stat().st_size>1024 or not valid_facts(json.loads(facts_path.read_text())): raise RuntimeError("missing bounded read evidence")
                if snapshot(state)!=before or (state/"model-stages.jsonl").read_text().splitlines()!=calls or not verify_records(state): raise RuntimeError("History reads changed records or model-call count")
                stack._stop_owned_process_group(web);web=None;stack._stop(api);api=None
                print("Completed History connected: 1 scenario, 2 browser phases PASS; 2 owners and source identities; foreign/missing 404; anonymous 401; unchanged records and model calls; cleanup PASS")
                return 0
        finally:
            stack._stop_owned_process_group(web)
            stack._stop(api)


def main():
    p=argparse.ArgumentParser();p.add_argument("mode",choices=("run","serve"));p.add_argument("--api-port",type=int,default=18478);p.add_argument("--web-port",type=int,default=13478);p.add_argument("--state-dir");args=p.parse_args()
    if args.mode=="serve":
        state=Path(args.state_dir).resolve() if args.state_dir else None
        if not state or not state.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not state.name.startswith("ask4mo_story_connected_") or not state.is_dir() or (state/"journey.db").exists(): raise SystemExit("fresh disposable test directory required")
        return serve(args)
    return run(args)
if __name__=="__main__": raise SystemExit(main())
