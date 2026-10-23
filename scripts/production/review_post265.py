"""Frozen post-PR-265 review probes: synthetic temp stores and mocked models only.

Reproduce the recorded migration and settlement-overlap observations without
opening development databases, contacting providers, or overwriting evidence.
The runtime must still match reviewed main aedbef3d for these probes to apply.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: F401 - isolate every runtime import from .env and real stores
import os, json, tempfile, asyncio, threading
from datetime import datetime, timezone
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, MetaData, Table, select, text, inspect
from src.persistence import Base, User, AIUsageFact, make_engine, make_session_factory
from src.agent.models import AgentRunRequest
from src.agent.eval import build_eval_career
from src.application.agent_service import AgentApplicationService
from src.privacy.preparation import PreparationRunIndex
from tests.test_agent_streaming_04c import Model


def migration_probe():
    with tempfile.TemporaryDirectory(prefix="ask4mo-post265-migrations-") as d:
        url = "sqlite:///" + str(Path(d) / "migration.sqlite")
        os.environ["DATABASE_URL"] = url
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "0027_email_attempts")
        engine = create_engine(url)
        users = Table("users", MetaData(), autoload_with=engine)
        with engine.begin() as c:
            c.execute(
                users.insert().values(
                    id=1,
                    subject="synthetic-keep",
                    provider="test",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        command.upgrade(cfg, "0047_workspace_ownership_transfers")

        def counts():
            with engine.connect() as c:
                return {
                    n: c.execute(text('SELECT COUNT(*) FROM "' + n + '"')).scalar()
                    for n in inspect(engine).get_table_names()
                    if n != "alembic_version"
                }

        old = counts()
        command.upgrade(cfg, "head")
        new = counts()
        assert all(new[n] == v for n, v in old.items())
        control = Table("agent_run_controls", MetaData(), autoload_with=engine)
        with engine.begin() as c:
            c.execute(
                control.insert().values(
                    run_id="synthetic-control",
                    owner_user_id=1,
                    status="running",
                    settled=False,
                    deadline_epoch=1,
                )
            )
        refused = False
        try:
            command.downgrade(cfg, "0047_workspace_ownership_transfers")
        except RuntimeError:
            refused = True
        assert refused
        with engine.connect() as c:
            assert (
                c.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == "0048_agent_run_controls"
            )
            assert c.execute(select(control.c.run_id)).scalar() == "synthetic-control"
        with engine.begin() as c:
            c.execute(control.delete())
        command.downgrade(cfg, "0047_workspace_ownership_transfers")
        assert counts() == old
        command.upgrade(cfg, "head")
        engine.dispose()
        return {
            "mode": "synthetic temporary SQLite only",
            "from_revision": "0027_email_attempts",
            "target_revision": "0048_agent_run_controls",
            "original_database_opened": False,
            "existing_0047_table_row_counts_preserved": True,
            "nonempty_0048_downgrade_refused": True,
            "refused_downgrade_kept_revision_and_control": True,
            "empty_downgrade_preserved_other_rows": True,
            "reupgrade_succeeded": True,
            "postgresql_verification": "NOT RUN",
        }


def concurrency_probe():
    with tempfile.TemporaryDirectory(prefix="ask4mo-post265-concurrency-") as d:
        url = "sqlite:///" + str(Path(d) / "application.sqlite")
        engine = make_engine(url)
        Base.metadata.create_all(engine)
        sf = make_session_factory(engine)
        with sf() as s:
            s.add(User(id=1, subject="synthetic-one", provider="test"))
            s.commit()
        calls = []

        def build():
            return AgentApplicationService(
                model_factory=lambda: Model(calls=calls),
                career_service=build_eval_career(),
                database_url=url,
                run_index=PreparationRunIndex(sf),
                usage_session_factory=sf,
            )

        first, other = build(), build()
        entered, release = threading.Event(), threading.Event()
        record = first._record_usage

        def hold(result, owner):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("probe release timed out")
            return record(result, owner)

        first._record_usage = hold

        async def run():
            manager = first.streaming()
            rid = await manager.start(AgentRunRequest(goal="Hello", user_id="1"))
            assert await asyncio.to_thread(entered.wait, 5)
            before = manager.controls.owned(rid, "1")
            n = len(calls)
            try:
                result = await asyncio.to_thread(
                    other.continue_run, rid, "1", "Continue please"
                )
                accepted = result.run_id == rid
            finally:
                release.set()
                await asyncio.gather(*list(manager.tasks))
            with sf() as session:
                fact = session.scalar(
                    select(AIUsageFact).where(AIUsageFact.usage_key == "agent:" + rid)
                )
                recorded_calls = fact.model_calls if fact else None
                recorded_tokens = fact.total_tokens if fact else None
            return {
                "recorded_model_calls": recorded_calls,
                "recorded_total_tokens": recorded_tokens,
                "mode": "two service instances, same temporary SQLite/checkpoint stores, mocked model",
                "settled_at_concurrent_admission": before["settled"],
                "control_status_at_admission": before["status"],
                "concurrent_continue_accepted": accepted,
                "model_invocations_before": n,
                "model_invocations_after": len(calls),
                "real_provider_calls": 0,
                "expected_followup": "reject continuation/resume while producer settlement is pending using durable ownership state; verify across independent workers",
            }

        result = asyncio.run(run())
        engine.dispose()
        return result


def main() -> int:
    import argparse, subprocess

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="New report path; existing evidence is never overwritten",
    )
    args = parser.parse_args()
    if args.out.exists():
        parser.error("report path already exists")
    baseline = "aedbef3dee28a68b72bc526a1fca537a3da7bd8d"
    paths = [
        "src/application/agent_service.py",
        "src/application/agent_streaming.py",
        "src/agent/run_control.py",
        "migrations/versions/0048_agent_run_controls.py",
        "src/reporting/telemetry.py",
    ]
    if subprocess.run(
        ["git", "diff", "--quiet", baseline, "--", *paths], cwd=ROOT
    ).returncode:
        parser.error(
            "runtime differs from the frozen review baseline; review and revise the probe instead"
        )
    report = {
        "baseline_sha": baseline,
        "migration_0048": migration_probe(),
        "unsettled_continuation": concurrency_probe(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        "Synthetic migration and two-service review observations recorded; zero paid calls; no gate approved."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
