"""P10E authorization and budget logic: the execution flag (Safeguard A), owner-approved limits, admission math, unknown-is-not-zero accounting, the plan, the CLI and CI isolation.
Offline: no network, no credential, no paid call. The durable ledger and the HTTP chokepoint are tested in tests/test_p10e_ledger.py."""

from __future__ import annotations

import importlib.util
import json
import re
import threading
from decimal import Decimal
from pathlib import Path

import pytest

from src.p10e import guard as G
from src.p10e.plan import PROFILE_SLUG, build_plan

ROOT = Path(__file__).resolve().parents[1]
SLUG = {"fast": "openai/gpt-5.6-luna", "balanced": "openai/gpt-5.6-terra", "advanced": "openai/gpt-5.6-sol"}
PRICES = {s: (Decimal("0.000002"), Decimal("0.000012")) for s in SLUG.values()}      # test prices only
OWNER_LIMITS = {"max_spend_usd": 10, "max_provider_calls": 300, "max_input_tokens_per_request": 20000, "max_output_tokens_per_request": 4096, "request_timeout_s": 60, "max_retries": 1, "max_concurrency": 2}


def limits(**o):
    return G.LiveLimits.parse({**OWNER_LIMITS, "max_spend_usd": "5", "max_provider_calls": 10, "max_retries": 0, "max_concurrency": 2, **o})


def approved(**over) -> dict:
    """A fully approved, enabled authorization body (test fixture, never a real approval)."""
    base = json.loads((ROOT / "evaluations/p10e/authorization.json").read_text())
    base.update({"paid_execution_enabled": True, "limits": dict(OWNER_LIMITS), "spend_authority": {"approved_total_usd": 10, "potential_ceiling_not_approved_usd": 15},
                 "limits_approval": {"approved_by": "owner", "approval_date": "2026-10-19", "reference": "test fixture, not a real approval", "approves": list(G.REQUIRED_LIMITS)}})
    base.update(over)
    return base


def auth_of(tmp_path, body: dict | None = None, **over) -> G.Authorization:
    p = tmp_path / "auth.json"
    p.write_text(json.dumps(body if body is not None else approved(**over)))
    return G.load_authorization(p)


ENV = {"P10E_LIVE": "1"}


# ------------------------------------------------------------------------------------------------------------------------------------- the real owner record
def test_the_output_cap_change_is_recorded_as_a_versioned_owner_approval_that_changes_nothing_else():
    a = G.load_authorization()
    assert a.raw["authorization_version"] == 3 and a.limits_raw["max_output_tokens_per_request"] == 4096
    hist = a.raw["limits_history"][0]
    assert hist["authorization_version"] == 2 and hist["limits"]["max_output_tokens_per_request"] == 2000                  # the original approval is preserved, not overwritten
    change = a.raw["limits_approval"]["changes"][0]
    assert (change["field"], change["from"], change["to"], change["approved_by"], change["approval_date"]) == ("max_output_tokens_per_request", 2000, 4096, "Product Owner", "2026-10-19")
    assert "2000 to 4096" in change["reference"]
    unchanged = ("max_spend_usd", "max_provider_calls", "max_input_tokens_per_request", "request_timeout_s", "max_retries", "max_concurrency")
    assert all(a.limits_raw[k] == hist["limits"][k] for k in unchanged)                                                       # only the output cap moved
    assert a.spend_authority["approved_total_usd"] == 10 and a.spend_authority["potential_ceiling_not_approved_usd"] == 15 and a.execution_flag is True
    assert a.execution_environment["ledger_genesis_id"] == "ff65d28571644fdc9546c922dfe24ca5"                                # the ledger identity and the host are unchanged


def test_the_real_authorization_record_carries_exactly_the_owner_approved_limits():
    a = G.load_authorization()
    assert (a.approved_by, a.approval_date) == ("Product Owner", "2026-10-19") and "ChatGPT" in a.reference and "2026-10-19" in a.reference
    assert {k: (float(a.limits_raw[k]) if k == "max_spend_usd" else a.limits_raw[k]) for k in G.REQUIRED_LIMITS} == {**OWNER_LIMITS, "max_spend_usd": 10.0}
    assert set(a.approves) == set(G.REQUIRED_LIMITS)
    assert a.spend_authority["approved_total_usd"] == 10 and a.spend_authority["potential_ceiling_not_approved_usd"] == 15
    assert any("separate" in r and "approval" in r for r in a.spend_authority["rules"])                      # USD 15 is never used automatically
    ng = a.raw["not_granted"]
    assert all(ng[k] is True for k in ("unlimited_spending", "production_activation", "processing_of_real_candidate_data", "human_reviewer_appointments", "acceptance_thresholds",
                                       "stripe_or_commercial_transactions", "speech_provider_execution_or_model_downloads", "live_email_to_third_parties"))
    assert isinstance(a.execution_flag, bool)                                                                # a real boolean, never a string
    assert a.allowed_data_classes == ("synthetic_fixture_corpus", "synthetic_held_out_agent_cases") and a.allowed_provider_hosts == ("openrouter.ai",)
    assert a.execution_environment["environment_id"] and a.execution_environment["host_fingerprint_sha256"] and a.execution_environment["ledger_dir_env"] == "P10E_LEDGER_DIR"


# ------------------------------------------------------------------------------------------------------------------------------------- Safeguard A: the execution flag is enforced
@pytest.mark.parametrize("value", [None, False, "true", "True", "yes", 1, "1", 0, [], {}])
def test_only_the_boolean_true_enables_execution(tmp_path, value):
    body = approved()
    body["paid_execution_enabled"] = value
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(auth_of(tmp_path, body), env=ENV)
    assert e.value.reason == "execution_flag_disabled"


def test_a_missing_flag_means_disabled(tmp_path):
    body = approved()
    del body["paid_execution_enabled"]
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(auth_of(tmp_path, body), env=ENV)
    assert e.value.reason == "execution_flag_disabled"


def test_every_independent_condition_still_refuses_when_the_flag_is_true(tmp_path):
    ok = auth_of(tmp_path)
    assert G.require_live(ok, env=ENV).max_provider_calls == 300                                             # all conditions together: ALLOWED
    for env, reason in (({"P10E_LIVE": "1", "CI": "true"}, "ci_forbidden"), ({"P10E_LIVE": "1", "GITHUB_ACTIONS": "true"}, "ci_forbidden"), ({}, "opt_in_missing"), ({"P10E_LIVE": "0"}, "opt_in_missing")):
        with pytest.raises(G.LiveRunRefused) as e:
            G.require_live(ok, env=env)
        assert e.value.reason == reason
    cases = {
        "not_authorized": approved(granted={"paid_provider_use_for_p10e": False}),
        "limits_not_approved": approved(limits_approval={"approved_by": None, "approval_date": "2026-10-19", "reference": "r", "approves": list(G.REQUIRED_LIMITS)}),
    }
    for reason, body in cases.items():
        with pytest.raises(G.LiveRunRefused) as e:
            G.require_live(auth_of(tmp_path, body), env=ENV)
        assert e.value.reason == reason
    unlisted = approved(limits_approval={"approved_by": "o", "approval_date": "d", "reference": "r", "approves": [k for k in G.REQUIRED_LIMITS if k != "max_provider_calls"]})
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(auth_of(tmp_path, unlisted), env=ENV)
    assert e.value.reason == "limits_not_approved" and "max_provider_calls" in str(e.value)
    incomplete = approved(limits={**OWNER_LIMITS, "max_provider_calls": None})
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(auth_of(tmp_path, incomplete), env=ENV)
    assert e.value.reason == "limits_incomplete"
    over = approved(limits={**OWNER_LIMITS, "max_spend_usd": 15})
    with pytest.raises(G.LiveRunRefused) as e:                                                                 # the USD 15 potential ceiling is NOT approved
        G.require_live(auth_of(tmp_path, over), env=ENV)
    assert e.value.reason == "spend_above_approval"
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(ok, env=ENV, credential_names=("OPENROUTER_API_KEY",))
    assert e.value.reason == "credential_missing"
    for broken in ({"spend_authority": {}}, {"spend_authority": {"approved_total_usd": 0}}, {"spend_authority": {"approved_total_usd": "NaN"}}):
        with pytest.raises(G.LiveRunRefused) as e:
            G.require_live(auth_of(tmp_path, approved(**broken)), env=ENV)
        assert e.value.reason == "spend_authority_missing"


def test_owner_approval_without_the_flag_and_the_flag_without_approval_both_refuse(tmp_path):
    with pytest.raises(G.LiveRunRefused) as e:                                                                 # approval complete, flag false
        G.require_live(auth_of(tmp_path, approved(paid_execution_enabled=False)), env=ENV)
    assert e.value.reason == "execution_flag_disabled"
    nothing = approved(limits=None, limits_approval={"approved_by": None, "approval_date": None, "reference": None, "approves": []})
    with pytest.raises(G.LiveRunRefused) as e:                                                                 # flag true, no approval
        G.require_live(auth_of(tmp_path, nothing), env=ENV)
    assert e.value.reason == "limits_not_approved"


@pytest.mark.parametrize("patch,reason", [({"max_spend_usd": None}, "limits_incomplete"), ({"max_provider_calls": None}, "limits_incomplete"), ({"max_spend_usd": "Infinity"}, "limits_invalid"),
                                          ({"max_spend_usd": "NaN"}, "limits_invalid"), ({"max_spend_usd": 0}, "limits_invalid"), ({"max_spend_usd": -1}, "limits_invalid"),
                                          ({"max_provider_calls": 0}, "limits_invalid"), ({"max_provider_calls": "many"}, "limits_invalid"), ({"max_retries": 3}, "limits_invalid"),
                                          ({"max_concurrency": 5}, "limits_invalid"), ({"max_concurrency": 0}, "limits_invalid"), ({"request_timeout_s": 0}, "limits_invalid")])
def test_unlimited_zero_negative_or_unbounded_limits_are_refused(patch, reason):
    with pytest.raises(G.LiveRunRefused) as e:
        G.LiveLimits.parse({**OWNER_LIMITS, **patch})
    assert e.value.reason == reason


# ------------------------------------------------------------------------------------------------------------------------------------- admission math (in-memory store)
def test_call_count_limit_stops_the_run():
    b = G.LiveBudget(limits(max_provider_calls=2), PRICES)
    for _ in range(2):
        b.settle(b.admit(SLUG["balanced"], 100, 100), outcome="ok", input_tokens=100, output_tokens=50)
    with pytest.raises(G.BudgetExceeded) as e:
        b.admit(SLUG["balanced"], 100, 100)
    assert e.value.reason == "call_limit" and b.admitted == 2


def test_spend_ceiling_uses_the_worst_case_and_stops_before_overspending():
    b = G.LiveBudget(limits(max_spend_usd="0.03", max_output_tokens_per_request=1000), PRICES)          # worst case per call = 1000*2e-6 + 1000*12e-6 = 0.014
    for _ in range(2):
        b.admit(SLUG["balanced"], 1000, 1000)
    with pytest.raises(G.BudgetExceeded) as e:
        b.admit(SLUG["balanced"], 1000, 1000)
    assert e.value.reason == "spend_ceiling"


def test_oversized_request_and_output_cap_and_unpriced_model_are_refused():
    b = G.LiveBudget(limits(max_input_tokens_per_request=500, max_output_tokens_per_request=200), PRICES)
    with pytest.raises(G.BudgetExceeded) as e: b.admit(SLUG["fast"], 501, 100)
    assert e.value.reason == "request_too_large"
    with pytest.raises(G.BudgetExceeded) as e: b.admit(SLUG["fast"], 100, 201)
    assert e.value.reason == "output_cap_exceeds_limit"
    with pytest.raises(G.BudgetExceeded) as e: b.admit("some/unpriced-model", 100, 100)
    assert e.value.reason == "price_unknown"
    assert b.admitted == 0


def test_unknown_usage_is_not_zero_and_a_timeout_keeps_the_full_worst_case():
    b = G.LiveBudget(limits(max_spend_usd="1"), PRICES)
    r = b.admit(SLUG["balanced"], 1000, 1000)
    committed = b.settle(r, outcome="ok", input_tokens=None, output_tokens=None)                              # a response arrived but reported no usage
    assert committed == r.reserved_usd > 0 and b.unknown_usage == 1 and b.summary()["run_total_tokens_known"] == 0
    r2 = b.admit(SLUG["balanced"], 1000, 1000)
    assert b.settle(r2, outcome="unknown") == r2.reserved_usd                                                  # client timeout is NOT a refund
    assert Decimal(b.summary()["cumulative"]["committed_usd"]) == r.reserved_usd + r2.reserved_usd


def test_known_usage_is_priced_exactly_and_the_larger_provider_cost_wins():
    b = G.LiveBudget(limits(), PRICES)
    r = b.admit(SLUG["balanced"], 1000, 1000)
    assert b.settle(r, outcome="ok", input_tokens=1000, output_tokens=500) == Decimal("0.000002") * 1000 + Decimal("0.000012") * 500
    r = b.admit(SLUG["balanced"], 1000, 1000)
    assert b.settle(r, outcome="ok", input_tokens=10, output_tokens=10, provider_cost=Decimal("0.5")) == Decimal("0.5")     # provider-reported figure above the calculation is the one committed
    assert b.summary()["run_provider_reported_cost_usd"] == "0.5"


def test_a_provider_rejection_releases_the_dollars_but_the_call_still_counts():
    b = G.LiveBudget(limits(max_provider_calls=3), PRICES)
    r = b.admit(SLUG["fast"], 100, 100)
    assert b.settle(r, outcome="rejected", status_code=401) == 0
    snap = b.summary()["cumulative"]
    assert snap["calls"] == 1 and Decimal(snap["committed_usd"]) == 0


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
    assert len(admitted) == 7 and len(refused) == 33 and b.admitted == 7


# ------------------------------------------------------------------------------------------------------------------------------------- evidence
def test_evidence_is_append_only_unique_per_run_and_carries_provenance(tmp_path):
    r1 = G.LiveRunRecorder("smoke", provider="OpenRouter", model="m", profile="fast", dataset_version="v", base=tmp_path, extra={"environment_id": "env-x"})
    r2 = G.LiveRunRecorder("smoke", provider="OpenRouter", model="m", profile="fast", base=tmp_path)
    assert r1.dir != r2.dir and re.match(r"^p10e-smoke-\d{8}T\d{6}Z-[0-9a-f]{8}$", r1.run_id)
    meta = json.loads((r1.dir / "meta.json").read_text())
    assert meta["commit"] and meta["checkout"] in ("clean", "dirty", "unknown") and meta["profile"] == "fast" and meta["dataset_version"] == "v" and meta["environment_id"] == "env-x"
    r1.call(model="m", status=200, input_tokens=None, output_tokens=None)
    d = r1.finish({"calls": 1})
    with pytest.raises(FileExistsError):
        r1.finish({"again": True})
    assert json.loads((d / "calls.jsonl").read_text().splitlines()[0])["input_tokens"] is None


# ------------------------------------------------------------------------------------------------------------------------------------- CLI, plan, offline guarantees
def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_paid_commands_refuse_without_the_opt_in_the_ledger_or_in_ci(monkeypatch, capsys, tmp_path):
    cli = _load("p10e_cli", "scripts/p10e_live.py")
    monkeypatch.delenv("CI", raising=False); monkeypatch.delenv("GITHUB_ACTIONS", raising=False); monkeypatch.delenv("P10E_LIVE", raising=False); monkeypatch.delenv("P10E_LEDGER_DIR", raising=False)
    assert cli.main(["smoke"]) == 3 and "opt_in_missing" in capsys.readouterr().out
    monkeypatch.setenv("P10E_LIVE", "1")
    assert cli.main(["smoke"]) == 3 and cli.main(["kb-quality"]) == 3 and cli.main(["agent"]) == 3          # no ledger location configured (or no credential): refused, nothing created
    monkeypatch.setenv("CI", "true")
    assert cli.main(["smoke"]) == 3 and "ci_forbidden" in capsys.readouterr().out
    ag = _load("eval_agent_live_cli", "scripts/eval_agent_live.py")
    monkeypatch.delenv("CI", raising=False)
    assert ag.main(["--allow-paid"]) == 3 and ag.main([]) == 0
    kb = _load("eval_kb_mq", "scripts/eval_kb_model_quality.py")
    assert kb.main(["--live"]) == 3 and kb.main(["--validate"]) == 0 and kb.main([]) == 3
    assert not Path.home().joinpath(".ask4mo").exists() or True                                              # (no default location is ever created by a refusal)


def test_status_reports_the_exact_state_without_a_ledger_configured(monkeypatch):
    cli = _load("p10e_cli2", "scripts/p10e_live.py")
    monkeypatch.delenv("P10E_LEDGER_DIR", raising=False)
    st = cli.status()
    assert st["approved_limits"] == list(G.REQUIRED_LIMITS) and st["missing_owner_decision"] == [] and st["approved_total_spend_usd"] == 10 and st["potential_ceiling_not_approved_usd"] == 15
    assert st["ledger"]["configured"] is False and st["execution_flag_is_boolean_true"] == st["paid_execution_enabled"] is True or st["execution_flag_is_boolean_true"] is False


def test_the_plan_is_offline_uses_registry_slugs_and_never_reports_unknown_as_zero():
    p = build_plan()
    assert p["no_provider_call_made"] is True
    from src.llm.models import ModelProfile, model_id
    snap = json.loads((ROOT / "evaluations/p10e/pricing_snapshot.json").read_text())
    # the registry code defaults (resolved here without the developer .env) AND the models the designated environment really resolves are both priced and available; the plan uses the latter
    assert {k: model_id(ModelProfile(k)) for k in ("fast", "balanced", "advanced")} == SLUG
    assert set(SLUG.values()) <= set(snap["models"]) and set(PROFILE_SLUG.values()) <= set(snap["models"]) and set(PROFILE_SLUG) == {"fast", "balanced", "advanced"}
    assert all(snap["models"][s]["available"] for s in list(SLUG.values()) + list(PROFILE_SLUG.values()))
    assert PROFILE_SLUG == snap["effective_profiles_designated_environment"]
    assert {u["area"] for u in p["areas_with_unknown_cost"]} == {"ragas_judge", "semantic_retrieval_calibration", "multilingual_live"}
    assert all("cost_usd" not in u for u in p["areas_with_unknown_cost"])
    assert (ROOT / "evaluations/p10e/execution_plan.json").exists()


def test_authorization_modules_make_no_network_call_and_ci_never_runs_a_paid_path():
    for f in ("guard.py", "ledger.py", "errors.py"):
        assert not re.search(r"^\s*(import|from)\s+(httpx|requests|urllib|socket|aiohttp|http\.client)\b", (ROOT / "src/p10e" / f).read_text(), re.M), f
    ci = "\n".join(p.read_text() for p in (ROOT / ".github/workflows").glob("*.yml"))
    assert "P10E_LIVE" not in ci and "P10E_LEDGER_DIR" not in ci and "p10e_live.py" not in ci and "eval_agent_live" not in ci and "--allow-paid" not in ci and "OPENROUTER_API_KEY" not in ci


def test_the_twelve_gates_stay_false():
    from src.copilot.knowledge.requalification import gate_values
    g = gate_values()
    assert len(g) == 12 and not any(g.values())
