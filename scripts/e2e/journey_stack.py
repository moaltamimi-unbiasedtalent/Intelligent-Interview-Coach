#!/usr/bin/env python
"""04D: a REAL local stack for the Candidate journey (FastAPI + Next.js, temporary database, offline fixtures, NO provider call), and the runner that drives the
real-browser journey against it. Also the entry point for pointing the SAME journey at a hosted staging stack.

ONE journey definition (frontend/e2e/journey/definition.ts) runs in two modes:
  mocked : Playwright with the network mocked (always on in CI):          cd frontend && E2E_PORT=3132 npx playwright test e2e/candidate-journey-04d.spec.ts
  real   : the same steps against a real stack (this script, or staging):  python scripts/e2e/journey_stack.py run

Local real stack (default; nothing leaves the machine):
  python scripts/e2e/journey_stack.py run                       # healthy offline stack, all seven languages
  python scripts/e2e/journey_stack.py run --variant keyless     # a keyless backend: reproduces the original Start Interview failure (the journey is EXPECTED to stop there)
  python scripts/e2e/journey_stack.py run --variant provider_down
  python scripts/e2e/journey_stack.py run --languages en,de     # a subset
Ports are UNIQUE and refuse the live stack: API 8142 and web 3142 by default (never 3000, 3015, 8020, 8030). The database, the checkpoint file, the invitation codes and
the logs live in one temporary directory that is removed at the end (--keep to inspect). Processes are stopped by exact PID, never by pattern.

What is REAL: the FastAPI app and its authorization, the invitation gate (hosted-like: REGISTRATION_INVITATION_REQUIRED=true), SQLite persistence, the LangGraph agent
graph and its durable checkpoint, the interview state machine, prompting and strict-schema validation, the Next.js production build and a real Chromium.
What is MOCKED: every model reply (fixtures shared with the mocked mode). Provider mode is reported as "offline" by /capabilities (04D PR 2); the run is labelled
OFFLINE evidence and is never live-model qualification.

Pointing the journey at a hosted staging stack (NOT RUN in this wave: OD-HOSTED has not been decided):
  1. Issue one single-use invitation PER LANGUAGE you will run (Admin /admin/invitations, or scripts/issue_invitation.py against the staging database) and put the
     plaintext codes in a JSON file:  {"codes": ["<code1>", "<code2>", ...]}  (keep it outside the repository; it is a credential until used).
  2. cd frontend && JOURNEY_MODE=real BASE_URL=https://<staging web origin> JOURNEY_API_URL=https://<staging api origin>/api/v1 \
        JOURNEY_INVITATIONS_FILE=/path/to/codes.json JOURNEY_LANGUAGES=en,de \
        npx playwright test --config playwright.journey-real.config.ts
  Add JOURNEY_EXPECT_AI_MODE=live only for a stack with a governed live budget (the default expects the offline mode). This suite makes no budget decision.
  Notes: the stack must serve the offline fixture provider or a governed live budget. Registration is rate limited per IP
  (8 per hour), so run at most seven languages plus the one uninvited-refusal probe per hour per IP. Provider mode is read from /capabilities and recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FORBIDDEN_PORTS = {3000, 3015, 8020, 8030}
DEFAULT_API_PORT = 8142
DEFAULT_WEB_PORT = 3142
ALL_LANGUAGES = ("en", "de", "fr", "es", "it", "pt", "nl")
KEY_CANARY = "sk-or-v1-0123456789abcdef0123456789abcdef0123456789abcdef04D0CANARYWEB"      # a test value, never a credential (same value as frontend/e2e/journey/canary.ts)


def _check_ports(*ports: int) -> None:
    for p in ports:
        if p in FORBIDDEN_PORTS:
            raise SystemExit(f"port {p} belongs to the live stack and is refused")
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", p)) == 0:
                raise SystemExit(f"port {p} is already in use")


# ------------------------------------------------------------------ the API process (internal subcommand: serve)

def serve(args: argparse.Namespace) -> int:
    """Run the real FastAPI app in this process with fixture model replies. Isolation first: no .env, no Streamlit secrets, temp-only databases."""
    import tests.conftest  # noqa: F401  (isolation: scrubs provider env, disables .env, refuses non-temp engines)

    state = Path(args.state_dir).resolve()
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{state / 'journey.db'}",
        "COPILOT_DATA_DIR": str(state / "data"),
        "COPILOT_CHROMA_DIR": str(state / "data" / "chroma"),
        # HOSTED-LIKE: API_ENV=staging is fail-closed (no anonymous developer identity, an invitation is ALWAYS required, hosted configuration validation). The one
        # deliberate deviation is language activation, below.
        "API_ENV": "staging",
        "AGENT_COACH_ENABLED": "true",
        "EMAIL_PROVIDER": "memory",
        "FRONTEND_ORIGINS": f"http://localhost:{args.web_port}",
        "APP_BASE_URL": f"http://localhost:{args.web_port}",
        "BCRYPT_ROUNDS": "10",
    })
    if args.variant != "keyless":
        os.environ["ASK4MO_PROVIDER_MODE"] = "offline"            # the offline guard also refuses every non-loopback request
    (state / "data").mkdir(parents=True, exist_ok=True)

    from src.persistence import Base, make_engine, make_session_factory

    engine = make_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)
    _issue_invitations(make_session_factory(engine), state, args.invitations)

    from src.demo_live.guard import ProviderControl

    from src.api import dependencies as deps
    from src.api.main import app

    # Hosted environments offer only languages with a complete approved qualification record, and none is qualified yet, so a staging stack would refuse new
    # language-bearing activity (language_not_activated). This offline stack shows what development shows (every selectable language, labelled UNQUALIFIED).
    from src import language_activation as LA

    labelled = LA.Activation(mode=LA.MODE_LABELLED, offered=tuple(LA.ACTIVE_CANDIDATE_LOCALES), qualified=(),
                             locales={c: LA.LocaleStatus(c, 0, False, ("offline journey stack",)) for c in LA.ACTIVE_CANDIDATE_LOCALES}, file_error=None)
    LA.current = lambda *, today=None: labelled

    if ProviderControl._active is None:                          # keyless variant: no provider mode env, but the network stays closed
        ProviderControl("offline").install()

    from scripts.e2e import journey_fakes as F

    fixtures = F.load_fixtures()
    F.install_offline_interview_services(app, args.variant, fixtures)
    if args.variant in ("healthy", "provider_down"):
        from src.application import agent_service

        model = F.ScriptedAgentModel(args.variant, fixtures)
        agent_service._default_model_factory = lambda profile=None: model
        # Mo's tools are never called (the scripted model gives a plain answer), but building the agent resolves the Career service, whose vector store a hosted environment
        # REFUSES without embedding credentials (hash_embedder_not_allowed). Retrieval is therefore not exercised by this offline stack and the stub fails loudly if it is.
        deps.get_career_service = lambda request: F.NoRetrievalCareerService()
    # keyless: nothing is overridden. The real backend has no key and raises its own "not configured" error: the defect's environment.

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.api_port, log_level="warning")
    return 0


def _issue_invitations(session_factory, state: Path, count: int) -> None:
    from src.application import admin_audit as A
    from src.invitations import repository as R

    codes = []
    for _ in range(count):
        code = R.new_code()
        audit = A.build_audit(event_type=A.ADMIN_INVITATION_ISSUED, actor_user_id=None, request_id=None, target_type="invitation", origin="cli")
        R.InvitationRepository(session_factory).issue(code_hash=R.hash_code(code), ttl_days=1, email=None, issued_by_user_id=None, audit=audit)
        codes.append(code)
    target = state / "invitations.json"
    target.write_text(json.dumps({"codes": codes}), encoding="utf-8")
    os.chmod(target, 0o600)


# ------------------------------------------------------------------ the runner

def _wait(url: str, timeout: float, label: str) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit(f"{label} did not become ready at {url}")


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)                                # exact PID of a process this script started
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def run(args: argparse.Namespace) -> int:
    langs = [x.strip() for x in args.languages.split(",") if x.strip()]
    if any(x not in ALL_LANGUAGES for x in langs):
        raise SystemExit(f"languages must be among {', '.join(ALL_LANGUAGES)}")
    _check_ports(args.api_port, args.web_port)
    state = Path(tempfile.mkdtemp(prefix="ask4mo_journey_"))
    frontend = ROOT / "frontend"
    api = web = None
    code = 1
    try:
        api_env = dict(os.environ)
        api = subprocess.Popen([sys.executable, str(Path(__file__)), "serve", "--state-dir", str(state), "--variant", args.variant, "--api-port", str(args.api_port),
                                "--web-port", str(args.web_port), "--invitations", str(len(langs) + 1)],
                               cwd=str(ROOT), env=api_env, stdout=(state / "api.log").open("w"), stderr=subprocess.STDOUT)
        _wait(f"http://127.0.0.1:{args.api_port}/api/v1/health", 90, "API")
        web_env = dict(os.environ, NEXT_PUBLIC_API_BASE_URL=f"http://localhost:{args.api_port}/api/v1", NEXT_DIST_DIR=".next-journey", NEXT_TELEMETRY_DISABLED="1",
                       OPENROUTER_API_KEY=KEY_CANARY)      # a canary the key-hazard guard (e2e/key-hazard-04d.spec.ts) must NOT find in the browser output
        if not args.skip_build:
            subprocess.run(["npm", "run", "build"], cwd=str(frontend), env=web_env, check=True, stdout=(state / "web-build.log").open("w"), stderr=subprocess.STDOUT)
        web = subprocess.Popen(["npx", "next", "start", "-p", str(args.web_port)], cwd=str(frontend), env=web_env, stdout=(state / "web.log").open("w"), stderr=subprocess.STDOUT)
        _wait(f"http://localhost:{args.web_port}/", 60, "web")
        pw_env = dict(os.environ, JOURNEY_MODE="real", JOURNEY_VARIANT=args.variant, BASE_URL=f"http://localhost:{args.web_port}", JOURNEY_API_URL=f"http://localhost:{args.api_port}/api/v1",
                      JOURNEY_INVITATIONS_FILE=str(state / "invitations.json"), JOURNEY_LANGUAGES=",".join(langs), E2E_PORT=str(args.web_port))
        result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.journey-real.config.ts"], cwd=str(frontend), env=pw_env)
        code = result.returncode
    finally:
        _stop(web)
        _stop(api)
        if args.keep:
            print(f"kept {state}")
        else:
            shutil.rmtree(state, ignore_errors=True)                  # a directory this script created
    print(f"journey (real local stack, variant={args.variant}, OFFLINE fixtures, no provider call): exit {code}")
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "serve"):
        s = sub.add_parser(name)
        s.add_argument("--variant", choices=("healthy", "provider_down", "keyless"), default="healthy")
        s.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
        s.add_argument("--web-port", type=int, default=DEFAULT_WEB_PORT)
        if name == "run":
            s.add_argument("--languages", default=",".join(ALL_LANGUAGES))
            s.add_argument("--keep", action="store_true")
            s.add_argument("--skip-build", action="store_true")
        else:
            s.add_argument("--state-dir", required=True)
            s.add_argument("--invitations", type=int, default=8)
    a = p.parse_args(argv)
    return serve(a) if a.cmd == "serve" else run(a)


if __name__ == "__main__":
    raise SystemExit(main())
