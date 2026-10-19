"""Post-Sprint-4 — LIVE MODEL EVALUATION harness (offline parts only).

Tests the pure classification/aggregation, sanitised trace record/replay, the
paid-call guard and CLI arg handling. NO provider calls — the live path is never
exercised here (that is manual/paid).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

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


def test_hitl_frequency_metrics():
    obs = [
        Observation("a", "balanced", awaiting_human_input=True, pending_action_type="confirm_role"),
        Observation("b", "balanced", awaiting_human_input=True, pending_action_type="approve_memory"),
        Observation("c", "balanced", awaiting_human_input=False),
        Observation("d", "balanced", awaiting_human_input=False),
    ]
    m = le.hitl_frequency(obs)
    assert m["runs"] == 4 and m["runs_with_interrupt"] == 2
    assert m["interrupt_rate"] == 0.5
    assert m["interrupt_type_counts"] == {"confirm_role": 1, "approve_memory": 1}


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


# --- P10E-R1 correction: explicit terminal status, strict completion, per-case evidence -----------------------------------------------------------------


def test_terminal_status_is_explicit_and_unknown_is_never_success():
    assert le.terminal_status("completed") == "COMPLETED" and le.terminal_status("awaiting_human_input") == "AWAITING_HUMAN_INPUT"
    assert le.terminal_status("step_limit_reached") == "STEP_LIMIT_REACHED" and le.terminal_status("failed") == "FAILED"
    assert le.terminal_status("guard_refused") == "GUARD_REFUSED" and le.terminal_status("provider_error") == "PROVIDER_ERROR"
    assert le.terminal_status("something_new") == "OTHER:something_new" and le.terminal_status(None) == "OTHER:unknown"


def test_step_limit_and_expected_hitl_pause_do_not_count_as_normal_completion():
    case = _case(hitl_expected=True, hitl_type="APPROVE_MEMORY")
    paused = classify(case, Observation("p", "balanced", status="awaiting_human_input", awaiting_human_input=True, pending_action_type="APPROVE_MEMORY"))
    assert paused["completed"] is False and paused["terminal_status"] == "AWAITING_HUMAN_INPUT" and paused["hitl_ok"] and paused["hitl_pause_observed"] and paused["hitl_pause_expected"]
    stuck = classify(_case(), Observation("s", "balanced", status="step_limit_reached"))
    assert stuck["completed"] is False and stuck["terminal_status"] == "STEP_LIMIT_REACHED"
    done = classify(_case(), Observation("d", "balanced", status="completed"))
    assert done["completed"] is True
    m = aggregate([paused, stuck, done])
    assert m["completion_rate"] == 0.333 and m["step_limit_rate"] == 0.333 and m["hitl_pause_rate"] == 0.333 and m["expected_hitl_pause_rate"] == 1.0
    assert m["terminal_status_counts"] == {"AWAITING_HUMAN_INPUT": 1, "COMPLETED": 1, "STEP_LIMIT_REACHED": 1}


def test_per_case_evidence_makes_a_miss_diagnosable_and_carries_no_content():
    case = _case(required_tools=["AnalyzeJob", "SearchCareerKnowledge"], forbidden_tools=["BuildPlan"], retrieval_expected=True)
    r = classify(case, Observation("x", "balanced", tools_used=["AnalyzeJob", "BuildPlan"], retrieval_used=False, status="completed", latency_ms=5, input_tokens=10, output_tokens=4, total_tokens=14,
                                   response_text="PRIVATE TEXT"))
    assert r["tool_selection_ok"] is False and r["missing_required_tools"] == ["SearchCareerKnowledge"] and r["forbidden_tools_used"] == ["BuildPlan"]
    assert r["expected_tools"] == ["AnalyzeJob", "SearchCareerKnowledge"] and r["tools_used"] == ["AnalyzeJob", "BuildPlan"] and r["retrieval_expected"] and not r["retrieval_used"]
    assert r["input_tokens"] == 10 and r["output_tokens"] == 4 and r["latency_ms"] == 5
    assert "PRIVATE TEXT" not in json.dumps(r) and "response_text" not in r


def test_the_guard_refusal_and_provider_failure_are_not_reported_as_agent_outcomes(tmp_path):
    from src.p10e import live_runs as R

    rec = SimpleNamespace(dir=tmp_path)
    (tmp_path / "calls.jsonl").write_text(json.dumps({"status": 200}) + "\n" + json.dumps({"status": 502}) + "\n" + json.dumps({"error": "ReadTimeout"}) + "\n")
    calls = R._calls_since(rec, 1)
    assert len(calls) == 2 and [bool(c.get("error") or c.get("status") not in (None, 200)) for c in calls] == [True, True]
    assert R._calls_since(SimpleNamespace(dir=tmp_path / "missing"), 0) == []


def test_refine_case_marks_guard_refusal_and_provider_error_and_builds_sanitized_evidence():
    from src.p10e import live_runs as R

    base = classify(_case(), Observation("a", "balanced", status="failed", latency_ms=3))
    c, ev = R.refine_case(dict(base), [{"status": 502, "provider_cost_usd": None}], None, [])
    assert c["terminal_status"] == "PROVIDER_ERROR" and ev["provider_failures"] == 1 and ev["provider_calls"] == 1 and ev["provider_reported_cost_usd"] is None
    c, ev = R.refine_case(dict(base), [{"status": 200, "provider_cost_usd": "0.002"}], "call_limit", ["call_limit"])
    assert c["terminal_status"] == "GUARD_REFUSED" and ev["guard_refusal_reasons"] == ["call_limit"] and ev["provider_reported_cost_usd"] == "0.002"
    ok = classify(_case(), Observation("b", "balanced", status="completed"))
    c, ev = R.refine_case(dict(ok), [{"status": 200, "provider_cost_usd": "0.001"}, {"status": 429}], None, [])
    assert c["terminal_status"] == "COMPLETED" and ev["provider_failures"] == 1           # a retried transient failure does not rewrite a completed run
