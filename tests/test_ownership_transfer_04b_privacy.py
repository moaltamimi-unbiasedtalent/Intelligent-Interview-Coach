"""04B completion: privacy export and the reviewed-migration rule for the ownership-transfer table."""

from __future__ import annotations

import json

import pytest

from src import persistence as P
from src.ownership_transfer_repository import hash_token, transfer_email_hash
from tests._workspaces_04b_world import World, build_team  # noqa: F401


@pytest.fixture(name="team")
def _team():
    world = World()
    yield build_team(world)
    world.close()


def test_export_lists_only_the_callers_own_transfers_without_secrets(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    mine = w.get("mia", "/auth/account/export").json()["workspace_ownership_transfers"]
    assert [(t["workspace"], t["your_side"], t["status"]) for t in mine] == [("Alpha", "recipient", "pending")]
    assert [t["your_side"] for t in w.get("alice", "/auth/account/export").json()["workspace_ownership_transfers"]] == ["proposer"]
    for who in ("adam", "max", "olga", "ivan"):
        assert w.get(who, "/auth/account/export").json()["workspace_ownership_transfers"] == []
    blob = json.dumps(w.get("mia", "/auth/account/export").json())
    assert tok not in blob and hash_token(tok) not in blob and transfer_email_hash("mia@x.com") not in blob


def test_privacy_schema_exception_is_exact_and_bound_to_this_file_and_table(tmp_path):
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("eval_privacy_controls_for_04b_transfers", root / "scripts" / "eval_privacy_controls.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    assert "workspace_ownership_transfers" in ev.PRIVACY_TABLES                                       # the new table is protected from now on
    assert ev.REVIEWED_PRIVACY_MIGRATIONS["_workspace_ownership_transfers.py"] == frozenset({"workspace_ownership_transfers"})
    known = set(P.Base.metadata.tables)
    real = next((root / "migrations" / "versions").glob("*_workspace_ownership_transfers.py")).read_text(encoding="utf-8")
    assert ev.migration_tables_touched(real, known) & ev.PRIVACY_TABLES <= ev.REVIEWED_PRIVACY_MIGRATIONS["_workspace_ownership_transfers.py"]

    def offenders(name: str, body: str):
        d = tmp_path / name.replace(".", "_")
        d.mkdir()
        (d / name).write_text(body, encoding="utf-8")
        return ev.post_baseline_privacy_touches(d, known, baseline=0)

    # the exception covers exactly one file name and exactly one table: the same file touching any other privacy table, or another file touching this one, fails
    assert offenders("0099_workspace_ownership_transfers.py", 'def upgrade():\n    op.create_table("workspace_ownership_transfers")\n') == {}
    assert offenders("0098_workspace_ownership_transfers.py", 'def upgrade():\n    op.drop_table("share_grants")\n') == {"0098_workspace_ownership_transfers.py": ["share_grants"]}
    assert offenders("0097_other_change.py", 'def upgrade():\n    op.drop_table("workspace_ownership_transfers")\n') == {"0097_other_change.py": ["workspace_ownership_transfers"]}
