"""The Ask4Mo demo-knowledge readiness check (scripts/check_demo_knowledge.py).

Deterministic tests of the readiness LOGIC (helpers monkeypatched), so they run without
a built knowledge base: a populated environment reports READY / exit 0, and an empty
fresh-checkout environment reports NOT READY / exit 1 with the build guidance — never a
crash.
"""

from __future__ import annotations

import scripts.check_demo_knowledge as chk


def test_ready_environment_exits_zero(capsys, monkeypatch):
    monkeypatch.setattr(chk, "_sqlite_row_count", lambda path: 1000)
    monkeypatch.setattr(chk, "_vector_passage_count", lambda: 3528)
    monkeypatch.setattr(chk, "_run_smoke_query", lambda: (5, True, False, "structured_role"))

    code = chk.main()
    out = capsys.readouterr().out

    assert code == 0
    assert "Structured roles: READY" in out
    assert "Vector passages: 3,528" in out
    assert "Sources returned: 5" in out
    assert "CITATION PIPELINE:\nPASS" in out
    assert "DEMO KNOWLEDGE:\nREADY" in out


def test_empty_environment_exits_nonzero_with_build_guidance(capsys, monkeypatch):
    monkeypatch.setattr(chk, "_sqlite_row_count", lambda path: 0)
    monkeypatch.setattr(chk, "_vector_passage_count", lambda: 0)
    # No provider call; an empty KB yields insufficient evidence and no sources.
    monkeypatch.setattr(chk, "_run_smoke_query", lambda: (0, False, True, None))

    code = chk.main()
    out = capsys.readouterr().out

    assert code == 1
    assert "DEMO KNOWLEDGE:\nNOT READY" in out
    assert "CITATION PIPELINE:\nFAIL" in out
    # Actionable build guidance references real loader commands.
    assert "rebuild_vector_index" in out
    assert "gitignored" in out


def test_smoke_query_failure_is_reported_not_raised(capsys, monkeypatch):
    monkeypatch.setattr(chk, "_sqlite_row_count", lambda path: 1000)
    monkeypatch.setattr(chk, "_vector_passage_count", lambda: 100)

    def _boom():
        raise RuntimeError("retrieval broke")

    monkeypatch.setattr(chk, "_run_smoke_query", _boom)
    code = chk.main()
    out = capsys.readouterr().out
    assert code == 1  # never crashes; readiness fails safely
    assert "Smoke query could not run" in out
