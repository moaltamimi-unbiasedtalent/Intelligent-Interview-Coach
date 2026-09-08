"""Post-Sprint-4 — LIVE MODEL EVALUATION harness (offline parts only).

Tests the pure classification/aggregation, sanitised trace record/replay, the
paid-call guard and CLI arg handling. NO provider calls — the live path is never
exercised here (that is manual/paid).
"""

from __future__ import annotations

from src.agent import live_eval as le
from src.agent.live_eval import Observation, aggregate, classify


def _case(**over):
    base = {"id": "c", "goal": "g", "required_tools": [], "forbidden_tools": [],
            "retrieval_expected": False, "hitl_expected": False, "max_tool_calls": 2}
    base.update(over)
    return base


# --- classification ----------------------------------------------------------


def test_retrieval_case_correct_when_retrieval_ran():
    c = _case(required_tools=["SearchCareerKnowledge"], retrieval_expected=True)
    obs = Observation("c", "balanced", tools_used=["SearchCareerKnowledge"], retrieval_used=True)
    r = classify(c, obs)
    assert r["tool_selection_ok"] and r["retrieval_ok"] and not r["unnecessary_retrieval"]


def test_smalltalk_penalises_unnecessary_retrieval_and_forbidden_tool():
    c = _case(forbidden_tools=["SearchCareerKnowledge"], retrieval_expected=False, max_tool_calls=0)
    obs = Observation("c", "balanced", tools_used=["SearchCareerKnowledge"], retrieval_used=True)
    r = classify(c, obs)
    assert not r["tool_selection_ok"]          # forbidden tool used + over budget
    assert r["forbidden_tools_used"] == ["SearchCareerKnowledge"]
    assert r["unnecessary_retrieval"] and not r["retrieval_ok"]


def test_required_tool_missing_fails_recall():
    c = _case(required_tools=["AnalyzeJobDescription"])
    obs = Observation("c", "balanced", tools_used=[])
    r = classify(c, obs)
    assert not r["required_tool_recall_ok"] and not r["tool_selection_ok"]


def test_tool_budget_enforced():
    c = _case(required_tools=["AnalyzeJobDescription"], max_tool_calls=1)
    obs = Observation("c", "balanced", tools_used=["AnalyzeJobDescription", "GenerateInterviewQuestions"])
    r = classify(c, obs)
    assert not r["within_tool_budget"] and not r["tool_selection_ok"]


def test_hitl_type_must_match():
    c = _case(hitl_expected=True, hitl_type="confirm_role")
    ok = classify(c, Observation("c", "balanced", awaiting_human_input=True, pending_action_type="confirm_role"))
    wrong = classify(c, Observation("c", "balanced", awaiting_human_input=True, pending_action_type="approve_memory"))
    none = classify(c, Observation("c", "balanced", awaiting_human_input=False))
    assert ok["hitl_ok"] and not wrong["hitl_ok"] and not none["hitl_ok"]


# --- aggregation -------------------------------------------------------------


def test_aggregate_rates():
    results = [
        classify(_case(retrieval_expected=True, required_tools=["SearchCareerKnowledge"]),
                 Observation("a", "balanced", tools_used=["SearchCareerKnowledge"], retrieval_used=True, latency_ms=100)),
        classify(_case(forbidden_tools=["SearchCareerKnowledge"], max_tool_calls=0),
                 Observation("b", "balanced", tools_used=[], retrieval_used=False, latency_ms=50)),
    ]
    m = aggregate(results)
    assert m["cases"] == 2
    assert m["tool_selection_accuracy"] == 1.0
    assert m["retrieval_decision_accuracy"] == 1.0
    assert m["unnecessary_retrieval_rate"] == 0.0
    assert m["average_latency_ms"] == 75.0


# --- sanitised trace record / replay ----------------------------------------


def test_trace_round_trip_is_sanitised(tmp_path):
    obs = Observation("salary_range", "balanced", tools_used=["SearchCareerKnowledge"],
                      retrieval_used=True, latency_ms=120, total_tokens=None)
    le.save_trace(obs, traces_dir=tmp_path)
    loaded = le.load_traces(traces_dir=tmp_path)
    assert len(loaded) == 1 and loaded[0].case_id == "salary_range"
    # Trace holds only safe fields — never candidate text / reasoning / prompts.
    text = (tmp_path / "salary_range.json").read_text()
    for banned in ("goal", "chain_of_thought", "reasoning", "system", "prompt", "answer"):
        assert banned not in text


# --- CLI: paid guard + recorded scoring -------------------------------------


def test_cli_without_opt_in_does_not_run_live(capsys):
    from scripts import eval_agent_live as cli
    rc = cli.main(["--profile", "balanced"])  # no --allow-paid, no RUN_PAID_EVAL
    out = capsys.readouterr().out
    assert rc == 0
    assert "did NOT run" in out and "Configuration OK" in out


def test_cli_evaluate_recorded_offline(tmp_path, monkeypatch, capsys):
    from scripts import eval_agent_live as cli
    # Point trace loading at a temp dir with one recorded trace matching a real case id.
    monkeypatch.setattr(le, "TRACES_DIR", tmp_path)
    le.save_trace(Observation("salary_range", "balanced", tools_used=["SearchCareerKnowledge"],
                              retrieval_used=True, latency_ms=90), traces_dir=tmp_path)
    monkeypatch.setattr(cli, "load_traces", lambda: le.load_traces(traces_dir=tmp_path))
    rc = cli.main(["--evaluate-recorded"])
    out = capsys.readouterr().out
    assert rc == 0 and "recorded" in out and "tool_selection_accuracy" in out
