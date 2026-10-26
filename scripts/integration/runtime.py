"""Guarded synthetic-provider seam for an otherwise strict hosted API.

No language, identity, authorization, scanner or budget guard is replaced. The
only injected service uses the real graph/checkpointer/usage store with a local
scripted model and a retrieval seam that fails loudly. It is used for existing
synthetic run fixtures; new hosted language-bearing requests remain refused.
Normal application startup never imports this module.
"""

from __future__ import annotations
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def boundary():
    from sqlalchemy.engine import make_url

    token = os.environ.get("ASK4MO_DISPOSABLE_CAMPAIGN", "")
    url = make_url(os.environ.get("DATABASE_URL", ""))
    if not (
        re.fullmatch(r"[a-f0-9]{16}", token)
        and url.host == "db"
        and url.database == "p5b_recovery_campaign_" + token
        and url.get_backend_name() == "postgresql"
        and url.port == 5432
        and not url.query
        and url.username == "disposable"
        and url.password == "synthetic-test-only"
        and os.environ.get("ASK4MO_PROVIDER_MODE") == "offline"
        and os.environ.get("API_ENV") == "staging"
        and os.environ.get("EMAIL_PROVIDER") == "memory"
    ):
        raise RuntimeError("disposable_campaign_boundary_required")
    for key in (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "BREVO_API_KEY",
        "AI_BUDGET_APPROVED",
        "AI_BUDGET_CONFIG_PATH",
    ):
        if os.environ.get(key):
            raise RuntimeError("live_configuration_refused")
    return token


def control(*, increment=False, **updates):
    path = Path("/campaign/model.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        raw = f.read()
        state = (
            json.loads(raw) if raw else {"mode": "plain", "calls": 0, "entered": False}
        )
        if increment:
            state["calls"] += 1
        if updates or increment:
            state.update(updates)
            f.seek(0)
            f.truncate()
            json.dump(state, f)
            f.flush()
        return state


class FixtureModel:
    def bind_tools(self, schemas):
        return self

    def invoke(self, messages):
        from langchain_core.messages import AIMessage, ToolMessage

        state = control(increment=True, entered=True)
        mode = state["mode"]
        if mode == "slow":
            deadline = time.monotonic() + 60
            while control()["mode"] == "slow" and time.monotonic() < deadline:
                time.sleep(0.05)
        if mode in ("timeout", "rate_limit"):
            import httpx

            if mode == "timeout":
                raise httpx.ReadTimeout("synthetic_provider_timeout")
            request = httpx.Request("POST", "https://provider.invalid/synthetic")
            raise httpx.HTTPStatusError(
                "synthetic_rate_limit",
                request=request,
                response=httpx.Response(429, request=request),
            )
        if mode == "hitl" and not any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ProposePreparationMemory",
                        "args": {
                            "category": "strength",
                            "summary": "Synthetic campaign preparation fact",
                            "target_role": "Synthetic role",
                        },
                        "id": "campaign-proposal",
                    }
                ],
            )
        if mode == "slow":
            return AIMessage(
                content="Synthetic interrupted-response fixture."
            )  # intentionally unknown usage
        return AIMessage(
            content="Synthetic integration response; no AI quality claim.",
            usage_metadata={"input_tokens": 11, "output_tokens": 5, "total_tokens": 16},
        )


def agent():
    boundary()
    from src.persistence import make_engine, make_session_factory
    from src.application.agent_service import AgentApplicationService
    from src.application.memory_service import MemoryApplicationService
    from src.repository import MemoryRepository
    from src.privacy.preparation import PreparationRunIndex
    from scripts.e2e.journey_fakes import NoRetrievalCareerService

    sf = make_session_factory(make_engine(os.environ["DATABASE_URL"]))
    return AgentApplicationService(
        model_factory=lambda: FixtureModel(),
        career_service=NoRetrievalCareerService(),
        memory_service=MemoryApplicationService(MemoryRepository(sf)),
        database_url=os.environ["DATABASE_URL"],
        run_index=PreparationRunIndex(sf),
        usage_session_factory=sf,
    )


def serve():
    boundary()
    from src.api.main import app
    from src.api import dependencies as D

    shared = agent()
    app.dependency_overrides[D.get_agent_service] = lambda: shared
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False, log_level="warning")


if __name__ == "__main__":
    if sys.argv[1:] != ["serve"]:
        raise SystemExit(2)
    serve()
