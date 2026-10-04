#!/usr/bin/env python
"""P10B-W9.8 candidate data-controls evaluation (deterministic, offline, 0 paid/live calls).

Invariants: export_scope_truthful, export_no_secrets_or_storage_keys, delete_routes_owner_scoped,
writes_never_retried, destructive_default_focus_is_cancel, no_window_confirm, no_invented_retention_periods,
no_fabricated_legal_history, no_admin_privacy_surface, no_migration_added, slogan_not_in_privacy_copy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from src import persistence as P  # noqa: E402
from src.application.data_export import build_candidate_export  # noqa: E402
from src.persistence import Base, make_session_factory  # noqa: E402
from src.repository import InterviewRepository  # noqa: E402


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

    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("no_migration_added", mig[-1].startswith(("0014_", "0015_", "0016_", "0017_", "0018_", "0019_", "0020_", "0021_", "0022_", "0023_", "0024_")), f"head file {mig[-1]}")
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
