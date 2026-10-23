#!/usr/bin/env python
"""P10B-W9.8 candidate data-controls evaluation (deterministic, offline, 0 paid/live calls).

Invariants: export_scope_truthful, export_no_secrets_or_storage_keys, delete_routes_owner_scoped,
writes_never_retried, destructive_default_focus_is_cancel, no_window_confirm, no_invented_retention_periods,
no_fabricated_legal_history, no_admin_privacy_surface, no_unreviewed_privacy_schema_change, slogan_not_in_privacy_copy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (W10.14): importing the pytest isolation module redirects DATABASE_URL/Chroma to a temp directory, disables .env and makes any non-temp engine FAIL FAST,
# so this evaluator can never write a developer store.
import tests.conftest  # noqa: E402,F401

from sqlalchemy import create_engine  # noqa: E402

from src import persistence as P  # noqa: E402
from src.application.data_export import build_candidate_export  # noqa: E402
from src.persistence import Base, make_session_factory  # noqa: E402
from src.repository import InterviewRepository  # noqa: E402


# Migrations up to and including this revision were reviewed under the earlier "no migration added" rule (W9.8) and are historical. Every LATER migration, whatever its
# number, may not touch a table that holds candidate privacy, export, deletion or ownership data.
PRIVACY_BASELINE_REVISION = 39
PRIVACY_TABLES = frozenset({
    "users", "auth_sessions", "auth_tokens", "account_identities", "password_credentials", "user_preferences", "user_feedback", "legal_acceptances",
    "candidate_documents", "document_versions", "document_claims", "candidate_stories", "story_evidence", "opportunities",
    "interviews", "interview_sessions", "questions", "answers", "reports", "preparation_runs", "preparation_packs", "preparation_memories",
    "privacy_requests", "billing_account_closures", "share_grants", "workspaces", "workspace_memberships", "workspace_invitations",
    "workspace_ownership_transfers",
})


# Reviewed, narrow exceptions (04A): a migration whose file name ends with the key may touch EXACTLY the listed privacy tables and no other (anything else it
# touches, or any other migration touching any privacy table, still fails). Keyed by the stable name suffix, not by number, because migrations are re-chained
# (renumbered) at merge. 04A: archive, Opportunity link, self-confirmation, answer evidence and use attribution for stories (additive, fail-closed downgrade).
REVIEWED_PRIVACY_MIGRATIONS: dict[str, frozenset[str]] = {
    "_story_bank_completion.py": frozenset({"candidate_stories", "answers", "opportunities", "users"}),
    # 04B completion: a NEW table for the two-step ownership transfer (token and address stored only as hashes). It is itself an ownership-data table, so it is
    # protected from now on; this one file may create and drop it and touch nothing else (its foreign keys only reference workspaces and users). Additive, with a
    # fail-closed downgrade (refuses while any transfer row exists).
    "_workspace_ownership_transfers.py": frozenset({"workspace_ownership_transfers"}),
}


def migration_tables_touched(source: str, known_tables: set[str]) -> set[str]:
    """Known table names referenced by a migration's CODE (string literals only; the docstring and comments are ignored)."""
    import ast

    tree = ast.parse(source)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(getattr(tree.body[0], "value", None), ast.Constant):
        tree.body = tree.body[1:]                                                    # drop the module docstring
    # A ForeignKey / ForeignKeyConstraint TARGET ("users.id") only REFERENCES a table from a NEW child table; it neither alters nor reads it (03E1: an owner FK with ON DELETE CASCADE is how
    # a new table is erased with the account). Only that exact "<table>.<column>" form inside those two constructors is skipped; every other literal (create/alter/drop of the table,
    # op.create_foreign_key, SQL text) still counts.
    fk_targets: set[int] = set()
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        fn = call.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in ("ForeignKey", "ForeignKeyConstraint"):
            for arg in call.args:
                for node in ast.walk(arg):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r"[a-z_]+\.[a-z_]+", node.value):
                        fk_targets.add(id(node))
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in fk_targets]
    touched: set[str] = set()
    for text in literals:
        for table in known_tables:
            if text == table or re.search(rf"\b{re.escape(table)}\b", text):
                touched.add(table)
    return touched


def post_baseline_privacy_touches(versions_dir: Path, known_tables: set[str], baseline: int = PRIVACY_BASELINE_REVISION, privacy_tables: frozenset[str] = PRIVACY_TABLES) -> dict[str, list[str]]:
    """Migrations after the baseline that touch a privacy table: {file name: [tables]} (empty means the invariant holds)."""
    offenders: dict[str, list[str]] = {}
    for path in sorted(versions_dir.glob("0*.py")):
        number = int(path.name.split("_", 1)[0])
        if number <= baseline:
            continue
        hit = migration_tables_touched(path.read_text(encoding="utf-8"), known_tables) & privacy_tables
        for suffix, allowed in REVIEWED_PRIVACY_MIGRATIONS.items():
            if path.name.endswith(suffix):
                hit = hit - allowed
        if hit:
            offenders[path.name] = sorted(hit)
    return offenders


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    repo = InterviewRepository(sf)
    with sf() as s:
        u = P.User(subject="a", provider="password", email="a@ex.com", display_name="A")
        v = P.User(subject="b", provider="password", email="b@ex.com", display_name="B")
        s.add_all([u, v])
        s.flush()
        doc = P.CandidateDocument(user_id=u.id, title="CV")
        s.add(doc)
        s.flush()
        s.add(P.DocumentVersion(document_id=doc.id, version=1, original_filename="cv.txt",
                                mime_type="text/plain", size_bytes=3, storage_key="SECRET-KEY",
                                status="ready"))
        s.add(P.PreparationMemory(user_id=u.id, category="strength", summary="mine"))
        s.add(P.PreparationMemory(user_id=v.id, category="strength", summary="theirs"))
        s.commit()
        uid = u.id

    class _Acct:
        email, tier, status, email_verified = "a@ex.com", "basic", "active", True

    ex = build_candidate_export(user_id=uid, session_factory=sf, repo=repo, account=_Acct())
    text = repr(ex)
    check("export_scope_truthful",
          ex["format"] == "ask4mo.candidate-export.v1" and ex["scope"]["included"] and ex["scope"]["not_included"]
          and [m["summary"] for m in ex["memories"]] == ["mine"],
          "scope stated in the file; only the owner's rows")
    check("export_no_secrets_or_storage_keys",
          "SECRET-KEY" not in text and "storage_key" not in text and "password_hash" not in text and "theirs" not in text,
          "no storage keys, hashes or other users' rows")
    check("no_fabricated_legal_history", ex["legal_acceptance"] == {"recorded": False},
          "acceptance history is reported as not recorded, never invented")

    history = _read("src/api/routes/history.py")
    delete_block = history.split("def delete_interview")[1] if "def delete_interview" in history else ""
    check("delete_routes_owner_scoped",
          "get_current_user_id" in delete_block and "delete_interview_with_source(user_id" in delete_block,
          "identity from the session; repository filters by user_id")

    retry = _read("frontend/lib/api/retry.ts")
    idem = retry.split("function isIdempotent")[1].split("}")[0] if "function isIdempotent" in retry else ""
    check("writes_never_retried",
          '"GET"' in idem and all(v not in idem for v in ("POST", "PATCH", "PUT", "DELETE")),
          "only GET/HEAD are retried")

    # W10.2: the behaviour lives in ConfirmDialogBase (label-agnostic); ConfirmDialog adds localized labels.
    dialog = _read("frontend/components/ui/ConfirmDialogBase.tsx") + _read("frontend/components/ui/ConfirmDialog.tsx")
    check("destructive_default_focus_is_cancel", "cancelRef.current?.focus()" in dialog and 'role="alertdialog"' in dialog,
          "initial focus on Cancel; alertdialog semantics")

    center = _read("frontend/components/account/DataPrivacyCenter.tsx")
    check("no_window_confirm", "window.confirm" not in center and "confirm(" not in center.replace("onConfirm", "").replace("const confirm", "").replace("confirm =", ""),
          "uses the accessible ConfirmDialog")

    en = _read("frontend/lib/i18n/messages/w98/en.ts")
    check("no_invented_retention_periods",
          not re.search(r"\b\d+\s*(day|days|month|months|year|years)\b", en, re.I),
          "no numeric retention periods in candidate copy")
    check("slogan_not_in_privacy_copy", "Ask More" not in en, "slogan is not re-stated or translated here")

    admin = _read("src/api/routes/admin.py")
    check("no_admin_privacy_surface", "/privacy/data" not in admin and "export_candidate" not in admin,
          "W10 owns admin privacy operations")

    offenders = post_baseline_privacy_touches(ROOT / "migrations/versions", set(Base.metadata.tables))
    check("no_unreviewed_privacy_schema_change", not offenders,
          "no migration after the W9.8 baseline touches a candidate privacy, export, deletion or ownership table" if not offenders else f"privacy tables touched: {offenders}")

    # --- 05E: deletion completeness, audit allow-list, acceptance history (deterministic, in-memory) ---
    from types import SimpleNamespace

    from src import audit_allowlist as AL
    from src.application.account_deletion_service import AccountDeletionService
    from src.privacy import erasure
    from tests._erasure_world_05e import STATE_OVERRIDES, make_row

    check("erasure_inventory_is_complete", erasure.unclassified_user_like_columns() == [] and len(erasure.user_references()) >= 55,
          f"{len(erasure.user_references())} user-referencing columns derived from the schema; none unclassified")
    e2 = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e2)
    sf2 = make_session_factory(e2)
    with sf2() as s:
        victim, bystander = P.User(subject="v", provider="password", email="v@ex.com"), P.User(subject="b", provider="password", email="b@ex.com")
        s.add_all([victim, bystander])
        s.flush()
        refs = [r for r in erasure.user_references() if r.table != "preparation_runs"]
        for ref in refs:
            for owner in (victim.id, bystander.id):
                make_row(s.connection(), Base.metadata.tables[ref.table], **{ref.column: owner}, **STATE_OVERRIDES.get(ref.table, {}))
        s.commit()
        vid, bid = victim.id, bystander.id
    summary = AccountDeletionService(sf2, document_store=SimpleNamespace(delete=lambda k: True)).delete_account(vid)
    with sf2() as s:
        left = erasure.residual_references(s, vid)
        bystander_ok = all((s.execute(Base.metadata.tables[r.table].select().where(Base.metadata.tables[r.table].c[r.column] == bid)).first() is not None) for r in refs)
    check("account_deletion_leaves_no_reference_to_the_account", summary.sql_complete and not left and bystander_ok,
          f"every reference column swept; another account untouched; residual={left or 'none'}")
    try:
        AL.sanitize({"free_text_note": "x"}, strict=True)
        rejected = False
    except AL.AuditContextRejected:
        rejected = True
    clean, problems = AL.sanitize({"count": 1, "note": "x"}, strict=False)
    check("audit_context_is_allow_list_enforced", rejected and clean == {"count": 1, "dropped_keys": 1}, "an unlisted key is rejected in strict mode and dropped (never stored) otherwise")
    legal_src = _read("src/privacy/legal.py")
    check("acceptance_history_is_never_backfilled_or_consent", "optional_processing_consent_recorded" in legal_src and '"back_filled": False' in legal_src,
          "history states it is a version acknowledgement only, not consent, not back-filled")
    return out


def main() -> int:
    print("ASK4MO - P10B-W9.8 PRIVACY CONTROLS EVALUATION\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:40s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
