"""P10E live-run safety: the owner authorization record, the budget and call-count guard, unknown-is-not-zero accounting, the LangChain callback (including nested calls),
append-only evidence, the guarded smoke and KB-quality runners, and CI isolation. Offline: fake chat models only, no network, no credential, no paid call."""

from __future__ import annotations

import importlib.util
import json
import re
import threading
from decimal import Decimal
from pathlib import Path

import pytest

from src.p10e import guard as G
from src.p10e import live_runs as L
from src.p10e.plan import PROFILE_SLUG, build_plan

ROOT = Path(__file__).resolve().parents[1]
SLUG = {"fast": "openai/gpt-5.6-luna", "balanced": "openai/gpt-5.6-terra", "advanced": "openai/gpt-5.6-sol"}
PRICES = {s: (Decimal("0.000002"), Decimal("0.000012")) for s in SLUG.values()}      # test prices only


def limits(**o):
    raw = {"max_spend_usd": "5", "max_provider_calls": 10, "max_input_tokens_per_request": 20000, "max_output_tokens_per_request": 2000, "request_timeout_s": 60, "max_retries": 0, "max_concurrency": 2, **o}
    return G.LiveLimits.parse(raw)


def auth_file(tmp_path, **o):
    raw = json.loads((ROOT / "evaluations/p10e/authorization.json").read_text())
    raw.update(o)
    p = tmp_path / "auth.json"
    p.write_text(json.dumps(raw))
    return G.load_authorization(p)


APPROVED = {"limits": {"max_spend_usd": 5, "max_provider_calls": 50, "max_input_tokens_per_request": 20000, "max_output_tokens_per_request": 2000, "request_timeout_s": 60, "max_retries": 1, "max_concurrency": 2},
            "spend_authority": {"approved_total_usd": 10, "potential_ceiling_not_approved_usd": 15},
            "limits_approval": {"approved_by": "owner", "approval_date": "2026-10-20", "reference": "test fixture, not a real approval", "approves": list(G.REQUIRED_LIMITS)}}


# ------------------------------------------------------------------------------------------------------------------------------------- the owner authorization record
def test_the_authorization_record_approves_ten_usd_total_and_nothing_else():
    a = G.load_authorization()
    assert a.owner_decision_date == "2026-10-19" and a.paid_use_granted is True
    assert (a.approved_by, a.approval_date, a.reference) == ("Product Owner", "2026-10-19", "Owner budget decision in ChatGPT, 2026-10-19")
    assert a.limits_raw["max_spend_usd"] == 10 and a.spend_authority["approved_total_usd"] == 10 and a.spend_authority["potential_ceiling_not_approved_usd"] == 15
    assert a.approves == ("max_spend_usd",)                                                              # ONLY the spend is approved
    others = [k for k in G.REQUIRED_LIMITS if k != "max_spend_usd"]
    assert all(a.limits_raw[k] is None for k in others)                                                  # engineering did not invent any other limit
    assert "NOT the approved" in a.spend_authority["decision"] or "NOT the approved spending limit" in a.spend_authority["decision"]
    assert any("separate, explicit owner approval" in r for r in a.spend_authority["rules"])
    ng = a.raw["not_granted"]
    assert all(ng[k] is True for k in ("unlimited_spending", "production_activation", "processing_of_real_candidate_data", "human_reviewer_appointments", "acceptance_thresholds",
                                       "stripe_or_commercial_transactions", "speech_provider_execution_or_model_downloads", "live_email_to_third_parties"))
    assert a.raw["paid_execution_enabled"] is False
    with pytest.raises(G.LiveRunRefused) as e:
        G.LiveLimits.parse(a.limits_raw)
    assert e.value.reason == "limits_incomplete"                                                         # the USD 10 alone does not enable anything
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(a, env={"P10E_LIVE": "1"})
    assert e.value.reason == "limits_not_approved" and "max_provider_calls" in str(e.value) and "max_spend_usd" not in str(e.value).split("yet:")[1]


def test_a_limit_must_be_listed_as_approved_and_spend_cannot_exceed_the_approved_total(tmp_path):
    env = {"P10E_LIVE": "1"}
    full = {**APPROVED, "limits_approval": {**APPROVED["limits_approval"], "approves": ["max_spend_usd"]}}
    with pytest.raises(G.LiveRunRefused) as e:                                                         # values present but not approved by the owner
        G.require_live(auth_file(tmp_path, **full), env=env)
    assert e.value.reason == "limits_not_approved"
    over = {**APPROVED, "limits": {**APPROVED["limits"], "max_spend_usd": 15}}
    with pytest.raises(G.LiveRunRefused) as e:                                                         # the USD 15 potential ceiling is NOT approved
        G.require_live(auth_file(tmp_path, **over), env=env)
    assert e.value.reason == "spend_above_approval"
    ten = {**APPROVED, "limits": {**APPROVED["limits"], "max_spend_usd": 10}}
    assert G.require_live(auth_file(tmp_path, **ten), env=env).max_spend_usd == Decimal(10)
    for broken in ({"spend_authority": {}}, {"spend_authority": {"approved_total_usd": 0}}, {"spend_authority": {"approved_total_usd": "NaN"}}):
        with pytest.raises(G.LiveRunRefused) as e:
            G.require_live(auth_file(tmp_path, **{**APPROVED, **broken}), env=env)
        assert e.value.reason == "spend_authority_missing"


def test_the_approved_total_is_cumulative_across_runs(tmp_path):
    def finished_run(committed, prior="0"):
        d = tmp_path / f"p10e-x-{committed}"
        d.mkdir()
        (d / "summary.json").write_text(json.dumps({"budget": {"committed_usd_upper_bound": committed, "prior_runs_committed_usd": prior}}))
    assert G.prior_committed_usd(tmp_path) == 0
    finished_run("3.5")
    finished_run("6.0", prior="3.5")                                                                     # a later run's total includes its prior: only its OWN spend (2.5) is added
    assert G.prior_committed_usd(tmp_path) == Decimal("3.5") + Decimal("2.5")
    b = G.new_budget(limits(max_spend_usd="10"), PRICES, tmp_path)
    assert b.prior_committed == Decimal("6.0") and Decimal(b.summary()["prior_runs_committed_usd"]) == Decimal("6.0")
    # worst case for 3000 in / 2000 out on a test price = 3000*2e-6 + 2000*12e-6 = 0.03: fine; but a ceiling already consumed refuses
    spent = G.LiveBudget(limits(max_spend_usd="10"), PRICES, prior_committed=Decimal("9.999"))
    with pytest.raises(G.BudgetExceeded) as e:
        spent.admit(SLUG["balanced"], 3000, 2000)
    assert e.value.reason == "spend_ceiling"


def test_an_unreadable_earlier_run_record_makes_the_guard_stricter_not_looser(tmp_path):
    d = tmp_path / "p10e-broken"
    d.mkdir()
    (d / "summary.json").write_text("{not json")
    assert G.prior_committed_usd(tmp_path) >= Decimal(10)                                                # counted as the full approved total


def test_require_live_refuses_for_every_missing_precondition(tmp_path):
    env = {"P10E_LIVE": "1"}
    ok = auth_file(tmp_path, **APPROVED)
    assert G.require_live(ok, env=env).max_provider_calls == 50
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(ok, env={"P10E_LIVE": "1", "CI": "true"}); assert e.value.reason == "ci_forbidden"
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(ok, env={"P10E_LIVE": "1", "GITHUB_ACTIONS": "true"}); assert e.value.reason == "ci_forbidden"
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(ok, env={}); assert e.value.reason == "opt_in_missing"
    for bad in ({"limits_approval": {"approved_by": None, "approval_date": "d", "reference": "r"}}, {"limits_approval": {"approved_by": "o", "approval_date": None, "reference": "r"}},
                {"limits_approval": {"approved_by": "o", "approval_date": "d", "reference": None}}):
        with pytest.raises(G.LiveRunRefused) as e:
            G.require_live(auth_file(tmp_path, **{**APPROVED, **bad}), env=env)
        assert e.value.reason == "limits_not_approved"
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(auth_file(tmp_path, **{**APPROVED, "granted": {"paid_provider_use_for_p10e": False}}), env=env); assert e.value.reason == "not_authorized"
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(ok, env=env, credential_names=("OPENROUTER_API_KEY",)); assert e.value.reason == "credential_missing"
    with pytest.raises(G.LiveRunRefused) as e:                                                       # the message names the credential, never a value
        G.require_live(ok, env={**env, "OPENROUTER_API_KEY": "  "}, credential_names=("OPENROUTER_API_KEY",))
    assert "sk-" not in str(e.value)


@pytest.mark.parametrize("patch,reason", [({"max_spend_usd": None}, "limits_incomplete"), ({"max_provider_calls": None}, "limits_incomplete"), ({"max_spend_usd": "Infinity"}, "limits_invalid"),
                                          ({"max_spend_usd": "NaN"}, "limits_invalid"), ({"max_spend_usd": 0}, "limits_invalid"), ({"max_spend_usd": -1}, "limits_invalid"),
                                          ({"max_provider_calls": 0}, "limits_invalid"), ({"max_provider_calls": "many"}, "limits_invalid"), ({"max_retries": 3}, "limits_invalid"),
                                          ({"max_concurrency": 5}, "limits_invalid"), ({"max_concurrency": 0}, "limits_invalid"), ({"request_timeout_s": 0}, "limits_invalid")])
def test_unlimited_zero_negative_or_unbounded_limits_are_refused(patch, reason):
    raw = {"max_spend_usd": 5, "max_provider_calls": 10, "max_input_tokens_per_request": 1000, "max_output_tokens_per_request": 500, "request_timeout_s": 30, "max_retries": 0, "max_concurrency": 1, **patch}
    with pytest.raises(G.LiveRunRefused) as e:
        G.LiveLimits.parse(raw)
    assert e.value.reason == reason


# ------------------------------------------------------------------------------------------------------------------------------------- budget and call-count enforcement
def test_call_count_limit_stops_the_run():
    b = G.LiveBudget(limits(max_provider_calls=2), PRICES)
    for _ in range(2):
        b.settle(SLUG["balanced"], b.admit(SLUG["balanced"], 100, 100), input_tokens=100, output_tokens=50, ok=True)
    with pytest.raises(G.BudgetExceeded) as e:
        b.admit(SLUG["balanced"], 100, 100)
    assert e.value.reason == "call_limit" and b.calls_admitted == 2


def test_spend_ceiling_uses_the_worst_case_and_stops_before_overspending():
    # worst case per call = 1000*2e-6 + 1000*12e-6 = 0.014; ceiling 0.03 admits two, refuses the third
    b = G.LiveBudget(limits(max_spend_usd="0.03", max_output_tokens_per_request=1000), PRICES)
    for _ in range(2):
        b.admit(SLUG["balanced"], 1000, 1000)
    with pytest.raises(G.BudgetExceeded) as e:
        b.admit(SLUG["balanced"], 1000, 1000)
    assert e.value.reason == "spend_ceiling"


def test_allowed_retries_multiply_the_worst_case():
    base = G.LiveBudget(limits(max_retries=0), PRICES)._worst_case(SLUG["fast"], 1000, 1000)
    assert G.LiveBudget(limits(max_retries=2), PRICES)._worst_case(SLUG["fast"], 1000, 1000) == base * 3


def test_oversized_request_and_output_cap_and_unpriced_model_are_refused():
    b = G.LiveBudget(limits(max_input_tokens_per_request=500, max_output_tokens_per_request=200), PRICES)
    with pytest.raises(G.BudgetExceeded) as e: b.admit(SLUG["fast"], 501, 100)
    assert e.value.reason == "request_too_large"
    with pytest.raises(G.BudgetExceeded) as e: b.admit(SLUG["fast"], 100, 201)
    assert e.value.reason == "output_cap_exceeds_limit"
    with pytest.raises(G.BudgetExceeded) as e: b.admit("some/unpriced-model", 100, 100)
    assert e.value.reason == "price_unknown"                                                          # a ceiling cannot be enforced without a price
    assert b.calls_admitted == 0


def test_unknown_usage_is_not_zero_the_worst_case_stays_committed():
    b = G.LiveBudget(limits(max_spend_usd="1"), PRICES)
    r = b.admit(SLUG["balanced"], 1000, 1000)
    b.settle(SLUG["balanced"], r, input_tokens=None, output_tokens=None, ok=True)
    s = b.summary()
    assert s["calls_with_unknown_usage"] == 1 and Decimal(s["cost_unknown_assumed_worst_case_usd"]) == r and r > 0
    assert Decimal(s["committed_usd_upper_bound"]) == r and s["total_tokens_known"] == 0              # the tokens are not reported as 0 consumed; the cost is not 0


def test_known_usage_is_priced_exactly_and_a_failed_call_without_usage_stays_reserved():
    b = G.LiveBudget(limits(), PRICES)
    r = b.admit(SLUG["balanced"], 1000, 1000)
    b.settle(SLUG["balanced"], r, input_tokens=1000, output_tokens=500, ok=True, latency_ms=12)
    assert b.spent_known == Decimal("0.000002") * 1000 + Decimal("0.000012") * 500 and b.in_flight == 0
    r2 = b.admit(SLUG["balanced"], 1000, 1000)
    b.settle(SLUG["balanced"], r2, input_tokens=None, output_tokens=None, ok=False)
    assert b.calls_failed == 1 and b.reserved_unknown == r2


def test_admission_is_thread_safe_exactly_the_limit_is_admitted():
    b = G.LiveBudget(limits(max_provider_calls=7, max_spend_usd="100"), PRICES)
    admitted, refused = [], []

    def go():
        try:
            b.admit(SLUG["fast"], 100, 100); admitted.append(1)
        except G.BudgetExceeded:
            refused.append(1)
    ts = [threading.Thread(target=go) for _ in range(40)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(admitted) == 7 and len(refused) == 33 and b.calls_admitted == 7


# ------------------------------------------------------------------------------------------------------------------------------------- the LangChain callback with fake models
def _fake(responses, usage=True, model_name=None):
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    def msgs():
        for r in responses:
            kw = {"usage_metadata": {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}} if usage else {}
            yield AIMessage(content=r, response_metadata={"model_name": model_name} if model_name else {}, **kw)
    return GenericFakeChatModel(messages=msgs())


def test_the_callback_enforces_the_call_limit_on_every_call_including_nested_ones():
    b = G.LiveBudget(limits(max_provider_calls=3, max_spend_usd="100"), PRICES)
    model = _fake(["a", "b", "c", "d"])
    model.callbacks = [G.make_guard_callback(b, SLUG["balanced"])]
    for _ in range(3):
        model.invoke([("human", "hi")])                                                                  # three model calls (as an agent's nested calls would be)
    with pytest.raises(G.BudgetExceeded) as e:
        model.invoke([("human", "hi")])
    assert e.value.reason == "call_limit" and b.calls_completed == 3 and b.input_tokens_known == 150 and b.output_tokens_known == 60


def test_the_callback_marks_missing_usage_unknown_and_records_provider_errors():
    b = G.LiveBudget(limits(max_spend_usd="100"), PRICES)
    model = _fake(["a"], usage=False)
    model.callbacks = [G.make_guard_callback(b, SLUG["fast"])]
    model.invoke([("human", "hi")])
    assert b.calls_with_unknown_usage == 1 and b.spent_known == 0 and b.reserved_unknown > 0

    class Boom(type(model)):
        def _generate(self, *a, **k):
            raise TimeoutError("provider timeout")
    bad = Boom(messages=iter([]))
    bad.callbacks = [G.make_guard_callback(b, SLUG["fast"])]
    with pytest.raises(TimeoutError):
        bad.invoke([("human", "hi")])
    assert b.calls_failed == 1 and b.in_flight == 0                                                      # a failed call releases its in-flight reservation (and stays committed as unknown)


def test_a_prompt_over_the_per_request_limit_never_reaches_the_model():
    b = G.LiveBudget(limits(max_input_tokens_per_request=100, max_spend_usd="100"), PRICES)
    model = _fake(["x"])
    model.callbacks = [G.make_guard_callback(b, SLUG["fast"])]
    with pytest.raises(G.BudgetExceeded) as e:
        model.invoke([("human", "word " * 500)])
    assert e.value.reason == "request_too_large" and b.calls_admitted == 0


# ------------------------------------------------------------------------------------------------------------------------------------- evidence
def test_evidence_is_append_only_unique_per_run_and_carries_provenance(tmp_path):
    r1 = G.LiveRunRecorder("smoke", provider="OpenRouter", model="m", profile="fast", dataset_version="v", base=tmp_path)
    r2 = G.LiveRunRecorder("smoke", provider="OpenRouter", model="m", profile="fast", base=tmp_path)
    assert r1.dir != r2.dir and re.match(r"^p10e-smoke-\d{8}T\d{6}Z-[0-9a-f]{8}$", r1.run_id)
    meta = json.loads((r1.dir / "meta.json").read_text())
    assert meta["commit"] and meta["checkout"] in ("clean", "dirty", "unknown") and meta["profile"] == "fast" and meta["dataset_version"] == "v" and meta["started_at"]
    r1.call(model="m", ok=True, input_tokens=None, output_tokens=None)
    d = r1.finish({"calls_admitted": 1})
    with pytest.raises(FileExistsError):
        r1.finish({"again": True})                                                                       # a run's summary is never overwritten
    assert json.loads((d / "calls.jsonl").read_text().splitlines()[0])["input_tokens"] is None             # UNKNOWN stays null, not 0
    with pytest.raises(FileExistsError):
        (r1.dir).mkdir(parents=True, exist_ok=False)


# ------------------------------------------------------------------------------------------------------------------------------------- guarded runners
def test_the_smoke_test_runs_through_the_guard_and_is_not_a_quality_claim(tmp_path):
    out = L.run_smoke(["balanced"], limits(max_provider_calls=3), prices=PRICES, base=tmp_path, build=lambda slug: _fake(["ok"], model_name=slug))
    r = out["results"]["balanced"]
    assert r["status"] == "OK" and r["usage_reported"] and r["unexpected_fallback"] is False and r["model"] == SLUG["balanced"]
    assert out["budget"]["calls_admitted"] == 1 and out["budget"]["total_tokens_known"] == 70
    summary = json.loads(next(tmp_path.iterdir()).joinpath("summary.json").read_text())
    assert "not quality qualification" in json.dumps(summary["results"])


def test_the_smoke_test_flags_an_unexpected_model_fallback_and_never_echoes_provider_text(tmp_path):
    out = L.run_smoke(["fast"], limits(), prices=PRICES, base=tmp_path, build=lambda slug: _fake(["ok"], model_name="someone/else-model"))
    assert out["results"]["fast"]["status"] == "FAILED" and out["results"]["fast"]["unexpected_fallback"] is True

    class Leaky(Exception):
        pass

    def build(slug):
        base = type(_fake(["ok"]))

        class Raising(base):
            def _generate(self, *a, **k):
                raise Leaky("Authorization: Bearer sk-or-SECRETSECRETSECRET")
        return Raising(messages=iter([]))
    out = L.run_smoke(["fast"], limits(), prices=PRICES, base=tmp_path, build=build)
    assert out["results"]["fast"] == {"status": "FAILED", "error_category": "Leaky"} and "sk-or" not in json.dumps(out)


def test_the_kb_quality_runner_answers_only_the_answer_cases_and_never_declares_a_pass(tmp_path):
    out = L.run_kb_quality("balanced", limits(max_provider_calls=50, max_spend_usd="50"), prices=PRICES, base=tmp_path,
                           build=lambda slug: _fake(["According to the evidence [1]."] * 20, model_name=slug))
    res = out["results"]
    assert len([c for c in res["cases"] if c["status"] == "COMPLETE"]) == 9 and len(res["evidence_cases_not_run"]) == 11
    assert res["metrics"]["thresholds"].startswith("none") and "citation_supports_claim" in res["metrics"]["pending_human_review"]
    packet = json.loads((Path(out["run_dir"]) / "review_packet.json").read_text())
    assert packet["reviewer"] is None and all(v == "PENDING_HUMAN_REVIEW" for c in packet["cases"] for v in c["human_ratings"].values())
    assert out["budget"]["calls_admitted"] == 9 and out["budget"]["refusals"] == []


def test_the_kb_quality_runner_stops_at_the_call_limit_and_says_so(tmp_path):
    out = L.run_kb_quality("fast", limits(max_provider_calls=3, max_spend_usd="50"), prices=PRICES, base=tmp_path, build=lambda slug: _fake(["Evidence [1]."] * 20, model_name=slug))
    done = [c for c in out["results"]["cases"] if c["status"] == "COMPLETE"]
    assert len(done) == 3 and out["results"]["stopped_by_guard"] == "call_limit" and out["budget"]["calls_admitted"] == 3
    assert any(c["status"].startswith("NOT RUN") for c in out["results"]["cases"])


# ------------------------------------------------------------------------------------------------------------------------------------- CLI, plan, offline guarantees
def _cli():
    spec = importlib.util.spec_from_file_location("p10e_live_cli", ROOT / "scripts/p10e_live.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_paid_commands_refuse_while_no_limits_are_approved(monkeypatch, capsys):
    cli = _cli()
    monkeypatch.delenv("CI", raising=False); monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("P10E_LIVE", "1")
    assert cli.main(["smoke"]) == 3 and cli.main(["kb-quality"]) == 3
    assert "limits_not_approved" in capsys.readouterr().out
    st = cli.status()
    assert st["paid_execution_possible"] is False and st["limits"] == "limits_incomplete" and st["approved_limits"] == ["max_spend_usd"]
    assert "max_spend_usd" not in st["missing_owner_decision"] and set(st["missing_owner_decision"]) == set(G.REQUIRED_LIMITS) - {"max_spend_usd"}      # the exact remaining blockers
    assert st["approved_total_spend_usd"] == 10 and st["potential_ceiling_not_approved_usd"] == 15
    spec = importlib.util.spec_from_file_location("eval_agent_live_cli", ROOT / "scripts/eval_agent_live.py")
    ag = importlib.util.module_from_spec(spec); spec.loader.exec_module(ag)
    assert ag.main(["--allow-paid"]) == 3 and ag.main([]) == 0                                              # offline behaviour is unchanged
    spec = importlib.util.spec_from_file_location("eval_kb_mq", ROOT / "scripts/eval_kb_model_quality.py")
    kb = importlib.util.module_from_spec(spec); spec.loader.exec_module(kb)
    assert kb.main(["--live"]) == 3 and kb.main(["--validate"]) == 0 and kb.main([]) == 3                   # P10D "NOT AUTHORISED" dry run is preserved


def test_the_plan_is_offline_uses_registry_slugs_and_never_reports_unknown_as_zero():
    p = build_plan()
    assert p["no_provider_call_made"] is True
    from src.llm.models import ModelProfile, model_id
    assert {k: model_id(ModelProfile(k)) for k in ("fast", "balanced", "advanced")} == PROFILE_SLUG == SLUG       # the price snapshot tracks the registry: drift fails this test
    snap = json.loads((ROOT / "evaluations/p10e/pricing_snapshot.json").read_text())
    assert set(snap["models"]) == set(SLUG.values()) and all(m["available"] for m in snap["models"].values())
    assert {u["area"] for u in p["areas_with_unknown_cost"]} == {"ragas_judge", "semantic_retrieval_calibration", "multilingual_live"}
    assert all("cost_usd" not in u for u in p["areas_with_unknown_cost"])                               # no zero stands in for an unknown cost
    assert Decimal(p["estimated_envelope_for_the_core_scope"]["cost_usd_low"]) <= Decimal(p["estimated_envelope_for_the_core_scope"]["cost_usd_high"])
    assert (ROOT / "evaluations/p10e/execution_plan.json").exists()


def test_guard_makes_no_network_call_and_ci_never_runs_a_paid_path():
    src = (ROOT / "src/p10e/guard.py").read_text()
    assert not re.search(r"httpx|requests\.|urllib|socket\.|aiohttp", src)
    ci = "\n".join(p.read_text() for p in (ROOT / ".github/workflows").glob("*.yml"))
    assert "P10E_LIVE" not in ci and "p10e_live.py" not in ci and "eval_agent_live" not in ci and "--allow-paid" not in ci and "OPENROUTER_API_KEY" not in ci


def test_the_twelve_gates_stay_false():
    from src.copilot.knowledge.requalification import gate_values
    g = gate_values()
    assert len(g) == 12 and not any(g.values())
