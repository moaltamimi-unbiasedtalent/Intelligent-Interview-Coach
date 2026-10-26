"""Task 07 boundary/regression tests: no real development data or provider calls."""

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from scripts.integration import campaign as C, runtime as T
from src.llm.budget import governor as G
from src.llm.budget.errors import BudgetError
from src.demo_live.guard import ProviderControl


def test_closed_governor_and_offline_guard_both_refuse_sync_async():
    G.uninstall()
    guard = ProviderControl("offline").install()
    sent = []
    transport = httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(200))
    try:
        G.install(
            G.BudgetGovernor.closed(
                "synthetic_no_approval", environ={"API_ENV": "staging"}
            )
        )
        with httpx.Client(transport=transport) as client:
            for url in (
                "https://openrouter.ai/api/v1/chat/completions",
                "https://api.openai.com/v1/embeddings",
                "https://unknown.invalid/anything",
            ):
                with pytest.raises(Exception):
                    client.post(url, json={})
            assert client.get("http://127.0.0.1/health").status_code == 200

        async def run():
            async with httpx.AsyncClient(transport=transport) as client:
                with pytest.raises(BudgetError):
                    await client.post(
                        "https://openrouter.ai/api/v1/chat/completions", json={}
                    )

        asyncio.run(run())
        assert len(sent) == 1 and sent[0].url.host == "127.0.0.1"
    finally:
        G.uninstall()
        guard.uninstall()


@pytest.mark.parametrize(
    "field,value",
    [
        ("DATABASE_URL", "sqlite:///original.db"),
        (
            "DATABASE_URL",
            "postgresql://disposable:synthetic-test-only@production/p5b_recovery_campaign_"
            + "a" * 16,
        ),
        (
            "DATABASE_URL",
            "postgresql+psycopg://disposable:synthetic-test-only@db:6432/p5b_recovery_campaign_"
            + "a" * 16,
        ),
        (
            "DATABASE_URL",
            "postgresql+psycopg://disposable:synthetic-test-only@db:5432/p5b_recovery_campaign_"
            + "a" * 16
            + "?options=unsafe",
        ),
        ("API_ENV", "development"),
        ("ASK4MO_PROVIDER_MODE", "live"),
        ("OPENAI_API_KEY", "synthetic-forbidden"),
        ("AI_BUDGET_CONFIG_PATH", "/owner/private.json"),
    ],
)
def test_fixture_boundary_refuses_live_or_private_configuration(
    monkeypatch, field, value
):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://disposable:synthetic-test-only@db:5432/p5b_recovery_campaign_"
        + "a" * 16,
    )
    for key, val in {
        "ASK4MO_DISPOSABLE_CAMPAIGN": "a" * 16,
        "API_ENV": "staging",
        "ASK4MO_PROVIDER_MODE": "offline",
        "EMAIL_PROVIDER": "memory",
    }.items():
        monkeypatch.setenv(key, val)
    assert T.boundary() == "a" * 16
    monkeypatch.setenv(field, value)
    with pytest.raises(RuntimeError):
        T.boundary()


def test_topology_keeps_image_identity_dependencies_isolation_and_security(tmp_path):
    manifest = {
        "application_sha": "a" * 40,
        "public_api_base_url": "https://" + C.API + "/api/v1",
        "build_started_at": "synthetic",
        "source": {
            "migration_chain": ["0048_agent_run_controls"],
            "compatible_schema_revisions": ["0048_agent_run_controls"],
            "budget_policy_version": 2,
            "recovery_policy_version": 1,
        },
        "images": {
            "application": {
                "image_id": "sha256:" + "b" * 64,
                "platform": "linux/amd64",
            },
            "web": {"image_id": "sha256:" + "c" * 64},
        },
    }
    topology = C.topology(
        manifest, {"operator_image_id": "sha256:" + "d" * 64}, tmp_path, "a" * 16
    )
    assert all(s["labels"][C.LABEL] == "a" * 16 for s in topology["services"].values())
    services = topology["services"]
    assert all(
        services[k]["image"] == manifest["images"]["application"]["image_id"]
        for k in ("api", "api_b", "worker", "worker_b", "migrate")
    )
    for k in ("api", "api_b", "worker", "worker_b"):
        assert (
            services[k]["depends_on"]["migrate"]["condition"]
            == "service_completed_successfully"
        )
        assert (
            services[k]["environment"]["API_ENV"] == "staging"
            and services[k]["environment"]["ASK4MO_PROVIDER_MODE"] == "offline"
        )
        assert services[k]["environment"]["AI_BUDGET_CONFIG_PATH"] == ""
    assert all(v["internal"] for v in topology["networks"].values())
    assert not services["caddy"].get("ports")
    assert all(not s.get("ports") for k, s in services.items() if k != "caddy")
    assert (
        services["probe"]["profiles"] == ["tools"]
        and "healthcheck" not in services["probe"]
    )
    assert services["migrate"]["command"] == ["bash", "scripts/migrate.sh"]
    assert all(v["labels"][C.LABEL] == "a" * 16 for v in topology["volumes"].values())


def test_local_tls_changes_preserve_security_policy():
    source = (C.ROOT / "deploy/Caddyfile").read_text()
    result = C.local_caddy(source)
    assert "email {$ACME_EMAIL}" not in result and result.count("tls internal") == 2
    assert (
        "script-src 'self'" in result
        and "script-src 'self' 'unsafe-inline'" not in result
    )
    for line in source.splitlines():
        if 'Content-Security-Policy "' in line or "header_up " in line:
            assert line in result


def test_capacity_refusal_creates_no_compose_resources(tmp_path, monkeypatch):
    args = argparse.Namespace(
        out=str(tmp_path / "new"), expected_sha="a" * 40, execute_disposable=True
    )
    campaign = C.Campaign(args)
    monkeypatch.setattr(C, "capacity", lambda: 1)
    monkeypatch.setattr(
        campaign, "compose", lambda *a, **k: pytest.fail("no stack must be created")
    )
    assert campaign.run() == 2 and not campaign.created
    summary = json.loads((Path(args.out) / "summary.json").read_text())
    assert summary["items"][0]["code"] == "insufficient_docker_capacity"
    assert summary["counts"]["FAIL"] == 1


def test_cleanup_refuses_foreign_volume_before_down(tmp_path, monkeypatch):
    c = C.Campaign(SimpleNamespace(out=str(tmp_path), expected_sha="a" * 40))
    c.created = True

    def command(args, **kwargs):
        if args[1:3] == ["ps", "-aq"]:
            return SimpleNamespace(stdout=b"")
        if args[1:3] == ["volume", "ls"]:
            return SimpleNamespace(stdout=b"foreign")
        if args[1:3] == ["volume", "inspect"]:
            return SimpleNamespace(stdout=b'[{"Labels": {}}]')
        raise AssertionError(args)

    monkeypatch.setattr(C, "command", command)
    monkeypatch.setattr(
        c,
        "compose",
        lambda *a, **k: pytest.fail("foreign resources must not be removed"),
    )
    with pytest.raises(C.CampaignError, match="ownership"):
        c.cleanup()


def test_existing_output_directory_is_never_overwritten(tmp_path, monkeypatch):
    original = tmp_path / "summary.json"
    original.write_text("existing-private-canary")
    campaign = C.Campaign(
        SimpleNamespace(
            out=str(tmp_path), expected_sha="a" * 40, execute_disposable=True
        )
    )
    monkeypatch.setattr(C, "capacity", lambda: pytest.fail("must refuse before Docker"))
    assert campaign.run() == 2 and not campaign.owns_directory
    assert original.read_text() == "existing-private-canary"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["summary.json"]


def test_internal_http_probe_uses_bounded_connection_and_preserves_contract(
    monkeypatch,
):
    from scripts.integration import probe as P

    calls = []

    class Response:
        status = 200

        def read(self):
            return b'{"synthetic":true}'

        def getheaders(self):
            return [("Content-Type", "application/json")]

    class Connection:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))

        def request(self, *args):
            calls.append(args)

        def getresponse(self):
            return Response()

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(P, "HTTPConnection", Connection)
    assert P.http("/api/v1/health") == (
        200,
        {"synthetic": True},
        {"Content-Type": "application/json"},
    )
    assert calls[0] == ("api", 8000, 35) and calls[-1] == "closed"
    with pytest.raises(P.ProbeFailure):
        P.http("/api/v1/health", host="outside.invalid")
