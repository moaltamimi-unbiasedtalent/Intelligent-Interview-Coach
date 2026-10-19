"""W12.4F Admin configuration completeness: the derived capability-readiness view, the speech state in the provider panel, and proof that Admin speech configuration is EFFECTIVE at its runtime consumer.

Offline and deterministic: temp databases, no network, no provider, no model, no secret. Nothing here claims a capability is live, qualified or production ready.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.application import admin_permissions as perm
from src.application.admin_readiness import QUALIFIERS, STATUSES, capability_readiness
from src.speech.governance import SpeechGovernanceService
from tests.test_admin_foundation_w10_1 import Env

ROOT = Path(__file__).resolve().parents[1]
API = "/api/v1"


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def _rows(env, role="platform_admin"):
    _, cookies = env.user(role)
    r = env.c.get(f"{API}/admin/readiness", cookies=cookies)
    assert r.status_code == 200, r.text
    return {c["id"]: c for c in r.json()["capabilities"]}, r.json()


# ------------------------------------------------------------------------------------------------------------------------------------------ readiness: RBAC and honesty
def test_readiness_requires_an_admin_permission(env):
    _, cand = env.user("user")
    assert env.c.get(f"{API}/admin/readiness", cookies=cand).status_code == 403


def test_platform_admin_sees_every_domain_with_a_canonical_status(env):
    rows, body = _rows(env)
    for rid in ("rbac", "secret_store", "integrations", "email_delivery", "identity_google_oidc", "ai_models", "knowledge", "speech_stt", "speech_tts", "billing", "platform_pause", "feature_flags", "rollout_gates"):
        assert rid in rows, rid
    for r in rows.values():
        assert r["status"] in STATUSES and set(r["qualifiers"]) <= set(QUALIFIERS) and r["basis"] in ("runtime", "code")
    assert body["vocabulary"]["statuses"] == list(STATUSES) and "not a statement that the platform is production ready" in body["boundary"]


def test_a_specialist_only_sees_rows_for_domains_they_can_read(env):
    rows, _ = _rows(env, "support_operator")
    assert "rbac" in rows and "rollout_gates" in rows
    assert not ({"billing", "integrations", "secret_store", "speech_stt", "ai_models", "knowledge"} & set(rows))


def test_nothing_unverified_is_reported_operational(env):
    rows, _ = _rows(env)
    for rid in ("speech_stt", "speech_tts"):
        assert rows[rid]["status"] != "OPERATIONAL" and {"LIVE_UNVERIFIED", "DEFERRED", "OFFLINE_VALIDATED"} <= set(rows[rid]["qualifiers"])
        assert "NOT_VERIFIED" in rows[rid]["evidence"] and "operational=False" in rows[rid]["evidence"]
    assert rows["billing"]["status"] == "MOCK" and "no payment provider is contacted" in " ".join(rows["billing"]["limitations"])
    assert rows["email_delivery"]["status"] != "OPERATIONAL" and "LIVE_UNVERIFIED" in rows["email_delivery"]["qualifiers"]
    assert rows["integrations"]["status"] == "PARTIAL" and rows["ai_models"]["status"] == "PARTIAL"
    assert "DEFERRED" in rows["knowledge"]["qualifiers"] and "Compensation V2 is disabled" in " ".join(rows["knowledge"]["limitations"])
    assert rows["rollout_gates"]["status"] == "READ_ONLY" and rows["rollout_gates"]["evidence"] == "12 of 12 gates are False." and rows["rollout_gates"]["admin_path"] is None


def test_readiness_carries_no_secret_path_or_candidate_content(env):
    _, body = _rows(env)
    raw = str(body)
    assert not re.search(r"sk-|api_key|/Users/|/Volumes/|/tmp/|Traceback|password", raw, re.I)


def test_an_unreadable_source_is_unavailable_never_healthy():
    class Broken:
        def __getattr__(self, name):
            raise RuntimeError("boom: /secret/path sk-123456")

    out = capability_readiness(allowed=frozenset(perm.PERMISSIONS), speech_runtime=Broken(), integrations=Broken(), secret_store=Broken(), billing_ops=Broken(), ai=Broken(), knowledge=Broken())
    rows = {r["id"]: r for r in out["capabilities"]}
    for rid in ("integrations", "secret_store", "ai_models", "knowledge", "billing", "speech"):
        assert rows[rid]["status"] == "CONFIGURED_BUT_UNAVAILABLE" and "UNAVAILABLE" in rows[rid]["qualifiers"]
    assert "boom" not in str(out) and "sk-" not in str(out)


def test_the_readiness_module_makes_no_network_call_and_has_no_write_path():
    src = (ROOT / "src/application/admin_readiness.py").read_text()
    assert not re.search(r"subprocess|os\.system|httpx|requests\.|socket\.|\bopen\(|\.commit\(|\.add\(|urlretrieve", src)
    assert "get_for_runtime" not in src                                                          # no secret value is ever read into a readiness row


def test_there_is_exactly_one_readiness_route_and_it_is_read_only():
    from src.api.admin_route_invariant import admin_routes
    mine = [r for r in admin_routes() if r.path.endswith("/admin/readiness")]
    assert len(mine) == 1 and tuple(mine[0].methods) == ("GET",)


# ------------------------------------------------------------------------------------------------------------------------------------------ provider panel
def test_provider_panel_reports_server_speech_without_claiming_it_runs(env):
    _, adm = env.user("platform_admin")
    j = env.c.get(f"{API}/admin/providers", cookies=adm).json()
    ss = j["speech"]["server_side"]
    assert ss["authorization_state"] == "not_authorized" and ss["stt_operational"] is False and ss["tts_operational"] is False
    assert ss["genuine_model_validation"] == {"openai_whisper": "NOT_VERIFIED", "kyutai_pocket_tts": "MODEL_EXECUTION_NOT_VERIFIED"}
    assert j["speech"]["architecture"] == "browser_web_speech"                                  # the active path is unchanged


# ------------------------------------------------------------------------------------------------------------------------------------------ effective configuration lifecycle (speech)
def test_speech_configuration_is_effective_at_the_runtime_consumer(env):
    _, cand = env.user("user")
    _, adm = env.user("platform_admin")
    _, support = env.user("support_operator")
    # 1. starting configuration, read through Admin and seen by the candidate runtime consumer
    start = env.c.get(f"{API}/admin/speech", cookies=adm).json()["config"]
    assert start["revision"] == 0 and start["browser_tts_allowed"] is True
    assert env.c.get(f"{API}/speech/capabilities", cookies=cand).json()["browser_tts_allowed"] is True
    # 2. unauthorized change is refused and changes nothing
    body = {"expected_revision": 0, "reason": "disable browser speech output for review", "browser_tts_allowed": False}
    assert env.c.put(f"{API}/admin/speech", json=body, cookies=support).status_code == 403
    assert env.c.get(f"{API}/admin/speech", cookies=adm).json()["config"]["revision"] == 0
    # 3. authorized change; read-back, audit, and the runtime consumer now observes it
    put = env.c.put(f"{API}/admin/speech", json=body, cookies=adm)
    assert put.status_code == 200 and put.json()["revision"] == 1 and put.json()["browser_tts_allowed"] is False
    assert env.c.get(f"{API}/admin/speech", cookies=adm).json()["config"]["browser_tts_allowed"] is False
    assert env.c.get(f"{API}/speech/capabilities", cookies=cand).json()["browser_tts_allowed"] is False
    ev = env.events("admin.speech_config_changed")
    assert len(ev) == 1 and ev[0]["context"]["changed"] == ["browser_tts_allowed"]
    # 4. unrelated settings are unchanged
    cfg = env.c.get(f"{API}/admin/speech", cookies=adm).json()["config"]
    assert cfg["browser_stt_allowed"] is True and cfg["stt_enabled"] is False and cfg["tts_enabled"] is False and cfg["languages"] == start["languages"]
    # 5. stale revision and invalid values
    assert env.c.put(f"{API}/admin/speech", json=body, cookies=adm).status_code == 409
    assert env.c.put(f"{API}/admin/speech", json={"expected_revision": 1, "reason": "x", "stt_timeout_seconds": 1000}, cookies=adm).status_code == 422
    assert len(env.events("admin.speech_config_changed")) == 1                                   # failed attempts wrote nothing
    # 6. restart persistence: a brand-new service over the same database sees the committed revision
    again = SpeechGovernanceService(env.accounts.session_factory, environment="development").get()
    assert again.revision == 1 and again.browser_tts_allowed is False
    # 7. enabling a provider is a recorded decision, not activation: readiness stays not operational
    assert env.c.put(f"{API}/admin/speech", json={"expected_revision": 1, "reason": "select for review", "stt_enabled": True}, cookies=adm).status_code == 200
    rows, _ = _rows(env)
    assert rows["speech_stt"]["status"] != "OPERATIONAL" and "DISABLED" not in rows["speech_stt"]["qualifiers"]
    assert env.c.get(f"{API}/speech/capabilities", cookies=cand).json()["server_stt_languages"] == []


def test_all_twelve_gates_remain_false_and_are_reported_read_only():
    from src.copilot.knowledge.requalification import gate_values
    g = gate_values()
    assert len(g) == 12 and not any(g.values())
