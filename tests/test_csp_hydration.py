"""Disposable CSP harness safeguards; no Docker, database or development stores."""

from argparse import Namespace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
import pytest
import hashlib
from scripts.csp import qualify as Q


def args(tmp_path):
    return Namespace(
        out=str(tmp_path / "fresh"), sha="a" * 40, manifest="absent", anchor="b" * 64
    )


def test_existing_output_is_never_overwritten(monkeypatch, tmp_path):
    a = args(tmp_path)
    out = Path(a.out)
    (out / "private").mkdir(parents=True)
    sentinel = out / "private/runtime.env"
    sentinel.write_text("private-canary")
    monkeypatch.setattr(Q.sys, "platform", "linux")
    monkeypatch.setattr(Q.argparse.ArgumentParser, "parse_args", lambda self: a)
    assert Q.main() == 1
    assert sentinel.read_text() == "private-canary"
    assert not (out / "summary.json").exists()


def test_native_docker_vm_host_is_explicitly_unqualified(monkeypatch, tmp_path):
    a = args(tmp_path)
    monkeypatch.setattr(Q.sys, "platform", "darwin")
    c = Q.Check(a)
    with pytest.raises(ValueError, match="linux_local_docker_host_required"):
        c.prepare()
    assert not Path(a.out).exists()


def test_cleanup_checks_stopped_containers_and_refuses_foreign_label(
    monkeypatch, tmp_path
):
    c = Q.Check(args(tmp_path))
    c.created = True
    calls = []

    def command(command, **kwargs):
        calls.append(command)
        if command[1:3] == ["container", "ls"]:
            assert "-a" in command
            return SimpleNamespace(stdout=b"foreign-container")
        return SimpleNamespace(
            stdout=json.dumps([{"Config": {"Labels": {Q.LABEL: "foreign"}}}]).encode()
        )

    monkeypatch.setattr(Q, "run", command)
    with pytest.raises(ValueError, match="cleanup_label_mismatch"):
        c.cleanup()
    assert not any("down" in command for command in calls)


def test_test_certificates_do_not_rewrite_any_security_or_proxy_directive():
    source = (Q.ROOT / "deploy/Caddyfile").read_text()
    local = Q.local_caddy(source)
    for line in source.splitlines():
        if any(
            key in line
            for key in (
                "Content-Security-Policy",
                "header_up",
                "Strict-Transport-Security",
                "X-Frame-Options",
                "Permissions-Policy",
                "Referrer-Policy",
            )
        ):
            assert line in local
    for line in source.splitlines():
        if line.lstrip().startswith("#"):
            assert line in local
    assert "tls internal" in local
    assert "auto_https disable_redirects" in local


def test_frontend_referrer_policy_is_one_explicit_no_referrer_value():
    source = (Q.ROOT / "deploy/Caddyfile").read_text()
    policies = [
        line.strip()
        for line in source.splitlines()
        if "Referrer-Policy" in line and not line.lstrip().startswith("#")
    ]
    assert policies == ['Referrer-Policy "no-referrer"']
    frontend = source.split("{$API_DOMAIN} {", 1)[0]
    assert 'Referrer-Policy "no-referrer"' in frontend
    assert Q.local_caddy(source).count('Referrer-Policy "no-referrer"') == 1


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:////tmp/csp.db",
        "postgresql+psycopg://disposable:synthetic-test-only@real-db:5432/p5b_csp_"
        + "a" * 16,
        "postgresql+psycopg://disposable:synthetic-test-only@db:5432/existing_database",
        "postgresql+psycopg://owner:private@db:5432/p5b_csp_" + "a" * 16,
        "postgresql+psycopg://disposable:synthetic-test-only@db:5432/p5b_csp_"
        + "a" * 16
        + "?sslmode=disable",
    ],
)
def test_seed_refuses_non_disposable_target_before_importing_auth(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ASK4MO_CSP_DISPOSABLE", "a" * 16)
    with pytest.raises(AssertionError):
        runpy.run_path(str(Q.ROOT / "scripts/csp/seed.py"))


@pytest.mark.parametrize("process_exit", [0, 1])
def test_browser_process_output_cannot_persist_form_credentials(
    monkeypatch, tmp_path, process_exit
):
    c = Q.Check(args(tmp_path))
    _qualified_browser_edge(monkeypatch, c)
    (c.out / "private").mkdir(parents=True)
    (c.out / "browser-after.json").write_text('{"passed": true}')
    c.compose = lambda *a, **k: SimpleNamespace(stdout=b"owned-container")

    def command(command, **kwargs):
        if command[:2] == ["docker", "inspect"]:
            return SimpleNamespace(
                stdout=json.dumps(
                    [
                        {
                            "NetworkSettings": {
                                "Networks": {"owned": {"IPAddress": "172.30.0.2"}}
                            }
                        }
                    ]
                ).encode()
            )
        return SimpleNamespace(
            stdout=b"form-password-canary",
            stderr=b"private-email-canary",
            returncode=process_exit,
        )

    monkeypatch.setattr(Q, "run", command)
    assert c.browser("after") is (process_exit == 0)
    assert c.summary["after_browser_exit"] == process_exit
    assert not list(c.out.rglob("*.log"))
    assert not any(b"canary" in p.read_bytes() for p in c.out.rglob("*") if p.is_file())


_REFERRER_PHASE = 'const expectedReferrerPolicy = before ? "strict-origin-when-cross-origin" : "no-referrer";'
_REFERRER_SINGLE = 'expect((await response.headersArray()).filter(h => h.name.toLowerCase() === "referrer-policy")).toHaveLength(1);'
_REFERRER_EXACT = 'expect(response.headers()["referrer-policy"]).toBe(expectedReferrerPolicy);'
_REFERRER_CURRENT_FRAGMENT = '["referrer-policy", expectedReferrerPolicy]'
_REFERRER_HISTORICAL_FRAGMENT = '["referrer-policy", "strict-origin-when-cross-origin"]'


def _assert_browser_security_assertions_preserved(source):
    lines = [line.strip() for line in source.splitlines()]
    # Admit only the reviewed phase-bound referrer expectation and two stronger
    # checks. Every historical assertion still has its original exact hash.
    for required in (_REFERRER_PHASE, _REFERRER_SINGLE, _REFERRER_EXACT):
        assert lines.count(required) == 1
        assert source.count(required) == 1
    assert source.count("expectedReferrerPolicy") == 3
    assert source.count(_REFERRER_CURRENT_FRAGMENT) == 1
    assert source.count(_REFERRER_HISTORICAL_FRAGMENT) == 0
    assertions = "\n".join(
        line.replace(_REFERRER_CURRENT_FRAGMENT, _REFERRER_HISTORICAL_FRAGMENT, 1)
        for line in lines
        if ("expect(" in line or "expect.poll(" in line)
        and line not in (_REFERRER_SINGLE, _REFERRER_EXACT)
    )
    # Reviewed baseline 291eb523: CSP, auth/cookies, nonce/spoof, negative payloads,
    # zero browser errors, external-call refusal and complete logout/revocation.
    assert hashlib.sha256(assertions.encode()).hexdigest() == (
        "74b14cef28c83c9020830613dcff7766beb4689f8b6a7b1fb05fb90a5517ae98"
    )


def test_all_existing_browser_security_assertions_are_preserved():
    source = (Q.ROOT / "frontend/csp/hydration.spec.ts").read_text()
    _assert_browser_security_assertions_preserved(source)
    assert 'retries: 0' in (Q.ROOT / "frontend/csp/playwright.config.ts").read_text()


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ('expect(nonce).toMatch(/^[A-Za-z0-9+/]{43}=$/);', 'expect(nonce).toBeTruthy();'),
        ('expect(nonce).toMatch(/^[A-Za-z0-9+/]{43}=$/);', ''),
        ('expect(loginRequests).toBe(1);', 'expect(loginRequests).toBe(0);'),
        ('expect(Boolean(cookie)).toBe(true);', ''),
        (_REFERRER_PHASE, ''),
        (_REFERRER_PHASE, _REFERRER_PHASE.replace('"no-referrer"', '"origin"')),
        (_REFERRER_PHASE, _REFERRER_PHASE + '\n' + _REFERRER_PHASE),
        (_REFERRER_SINGLE, ''),
        (_REFERRER_SINGLE, _REFERRER_SINGLE.replace('.toHaveLength(1)', '.toBeGreaterThan(0)')),
        (_REFERRER_SINGLE, _REFERRER_SINGLE + '\n' + _REFERRER_SINGLE),
        (_REFERRER_EXACT, ''),
        (_REFERRER_EXACT, _REFERRER_EXACT.replace('.toBe(', '.toContain(')),
        (_REFERRER_EXACT, _REFERRER_EXACT + '\n' + _REFERRER_EXACT),
        (
            _REFERRER_EXACT,
            _REFERRER_EXACT + '\nexpect(response.headers()["referrer-policy"]).toContain("no-referrer");',
        ),
        (_REFERRER_CURRENT_FRAGMENT, _REFERRER_CURRENT_FRAGMENT + ', ' + _REFERRER_CURRENT_FRAGMENT),
        (_REFERRER_CURRENT_FRAGMENT, '["referrer-policy", "no-referrer"]'),
    ],
    ids=[
        "altered-nonce-check",
        "missing-nonce-check",
        "altered-authentication-count",
        "missing-session-check",
        "missing-phase-definition",
        "weaker-phase-policy",
        "duplicate-phase-definition",
        "missing-single-header-check",
        "weaker-single-header-check",
        "duplicate-single-header-check",
        "missing-exact-policy-check",
        "weaker-exact-policy-check",
        "duplicate-exact-policy-check",
        "unapproved-additional-referrer-check",
        "duplicate-loop-fragment",
        "non-phase-bound-loop-fragment",
    ],
)
def test_browser_security_assertion_guard_rejects_unapproved_mutations(original, replacement):
    source = (Q.ROOT / "frontend/csp/hydration.spec.ts").read_text()
    assert source.count(original) == 1
    mutated = source.replace(original, replacement, 1)
    with pytest.raises(AssertionError):
        _assert_browser_security_assertions_preserved(mutated)


def test_failure_finally_retains_bounded_evidence_and_unbounded_error_counts():
    source = (Q.ROOT / "frontend/csp/hydration.spec.ts").read_text()
    final = source.split("} finally {", 1)[1]
    assert "result.diagnostics = diagnostics.snapshot()" in final
    assert "result.unexpected_console_errors = consoleErrors.length" in final
    assert "result.observed_external_attempts = external.length" in final
    assert 'writeFileSync(process.env.CSP_BROWSER_SUMMARY!' in final
    assert 'consoleErrors.length++' in source
    assert 'consoleErrors.push' not in source
    config = (Q.ROOT / "frontend/csp/playwright.config.ts").read_text()
    for field in ('trace: "off"', 'screenshot: "off"', 'video: "off"'):
        assert field in config


@pytest.mark.parametrize("value", ["private-canary", "ubuntu24 private-canary", "20261025.353.1\nprivate", ""])
def test_runner_metadata_is_not_an_environment_dump(value):
    assert Q.safe_runner_value(value) == "unavailable"


@pytest.mark.parametrize("value", ["ubuntu24", "20261025.353.1"])
def test_allowlisted_runner_metadata(value):
    assert Q.safe_runner_value(value) == value


def test_failure_summary_can_carry_safe_browser_diagnostics_without_process_output(monkeypatch, tmp_path):
    c = Q.Check(args(tmp_path))
    _qualified_browser_edge(monkeypatch, c)
    (c.out / "private").mkdir(parents=True)
    safe = {"passed": False, "stage": "nonce_rotation_and_spoof_refusal", "unexpected_console_errors": 13,
            "diagnostics": {"total_events": 13, "events": [{"text": "[redacted console error]"}]}}
    (c.out / "browser-after.json").write_text(json.dumps(safe))
    c.compose = lambda *a, **k: SimpleNamespace(stdout=b"owned-container")

    def command(command, **kwargs):
        if command[:2] == ["docker", "inspect"]:
            return SimpleNamespace(stdout=json.dumps([{"NetworkSettings": {"Networks": {"owned": {"IPAddress": "172.30.0.2"}}}}]).encode())
        return SimpleNamespace(stdout=b"password-canary", stderr=b"cookie-token-candidate-canary", returncode=1)

    monkeypatch.setattr(Q, "run", command)
    assert c.browser("after") is False
    assert c.summary["after"] == safe
    assert c.summary["after_browser_exit"] == 1
    assert "canary" not in json.dumps(c.summary)
    assert not list(c.out.rglob("*.log"))


def test_csp_database_revision_is_bound_to_reviewed_manifest():
    manifest = {"source": {"migration_chain": ["0048_agent_run_controls", "0049_workspace_mail_attempts"],
                           "compatible_schema_revisions": ["0049_workspace_mail_attempts"]}}
    expected = Q.expected_database_head(manifest)
    assert expected == "0049_workspace_mail_attempts"
    Q.require_database_head([expected], expected)
    for observed in ([], ["0048_agent_run_controls"], ["0050_future"], [expected, expected]):
        with pytest.raises(ValueError, match="unexpected_database_head"):
            Q.require_database_head(observed, expected)


@pytest.mark.parametrize("manifest", [None, {}, {"source": {}},
    {"source": {"migration_chain": [], "compatible_schema_revisions": []}},
    {"source": {"migration_chain": ["0049"], "compatible_schema_revisions": ["0048"]}},
    {"source": {"migration_chain": ["0049"], "compatible_schema_revisions": ["0049", "0050"]}},
    {"source": {"migration_chain": [None], "compatible_schema_revisions": [None]}},
])
def test_csp_refuses_missing_malformed_or_mismatched_reviewed_head(manifest):
    with pytest.raises(ValueError, match="invalid_manifest_schema"):
        Q.expected_database_head(manifest)


def test_lifecycle_diagnostics_project_only_safe_status_and_survive_probe_failure(monkeypatch, tmp_path):
    c = Q.Check(args(tmp_path))
    c.compose = lambda *a, **k: SimpleNamespace(stdout=b"private-container-id")
    calls = 0

    def inspect(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("private-secret-canary")
        return SimpleNamespace(stdout=json.dumps([{"State": {"Status": "running", "Health": {"Status": "healthy"}}, "Config": {"Env": ["private-secret-canary"]}}]).encode())

    monkeypatch.setattr(Q, "run", inspect)
    c.lifecycle_snapshot("hardened_ready")
    snapshot = c.summary["lifecycle_diagnostics"][0]
    assert snapshot["services"]["api"] == {"available": True, "status": "running", "health": "healthy"}
    assert snapshot["services"]["web"] == {"available": False}
    assert snapshot["services"]["caddy"] == {"available": True, "status": "running", "health": "healthy"}
    assert "private" not in json.dumps(snapshot)


def _qualified_browser_edge(monkeypatch, check):
    # These existing tests isolate the process-output boundary. Readiness itself
    # is exercised below, rather than bypassed in the production browser path.
    check._ready_edge = ("owned", "internal", "172.30.0.2", b"ca-identity")
    check._phase_ready = {phase: check._ready_edge for phase in ("before", "after")}
    check._phase_deadlines = {phase: Q.time.monotonic() + 90 for phase in ("before", "after")}
    monkeypatch.setattr(check, "edge_round", lambda evidence, **kw: (check._ready_edge, None, "ready"))
    monkeypatch.setattr(check, "edge_binding", lambda: check._ready_edge[:3])


@pytest.fixture
def edge_harness(monkeypatch, tmp_path):
    """Entire Docker/HTTPS boundary is controlled; no service or socket starts."""
    check = Q.Check(args(tmp_path))
    (check.out / "private").mkdir(parents=True)
    h = SimpleNamespace(
        check=check, clock=0, ip="172.30.0.2", network="owned-network",
        health={"api": "healthy", "web": "healthy"}, caddy_status="running",
        internal=True, foreign=False, malformed=False, ca_bad=False,
        probe_results={}, probes=[], commands=[], browser_calls=0, browser_exit=0,
        browser_summary={"passed": True}, on_probe=None, on_browser=None,
    )
    monkeypatch.setattr(Q, "READINESS_ATTEMPTS", 4)
    monkeypatch.setattr(Q.time, "monotonic", lambda: h.clock)
    monkeypatch.setattr(Q.time, "sleep", lambda seconds: setattr(h, "clock", h.clock + seconds))

    def context(_protocol):
        def load(*, cadata):
            assert cadata == "synthetic-public-ca-canary"
            if h.ca_bad:
                raise Q.ssl.SSLError("private-tls-error-canary")
        return SimpleNamespace(load_verify_locations=load, set_alpn_protocols=lambda protocols: protocols == ["http/1.1"])

    monkeypatch.setattr(Q.ssl, "SSLContext", context)

    def compose(*command, **kwargs):
        h.commands.append(command)
        if command[:2] == ("ps", "-q"):
            return SimpleNamespace(stdout=("owned-" + command[2]).encode())
        if command[:3] == ("exec", "-T", "caddy"):
            assert command[3:] == ("cat", "/data/caddy/pki/authorities/local/root.crt")
            return SimpleNamespace(stdout=b"synthetic-public-ca-canary")
        if command[:2] == ("exec", "-T") and command[3] == "curl":
            return SimpleNamespace(stdout=b"private-response-canary", returncode=0)
        if command[0] == "up":
            return SimpleNamespace(stdout=b"")
        raise AssertionError("unexpected fixture command")

    def command(command, **kwargs):
        h.commands.append(tuple(command))
        if command[:2] == ["docker", "inspect"]:
            if h.malformed:
                return SimpleNamespace(stdout=b"private-malformed-tool-canary")
            role = command[-1].removeprefix("owned-")
            state = {"Status": h.caddy_status if role == "caddy" else "running"}
            if role in h.health:
                state["Health"] = {"Status": h.health[role]}
            labels = {Q.LABEL: "foreign" if h.foreign else check.token,
                      "com.docker.compose.project": check.project}
            value = [{"Config": {"Labels": labels, "Env": ["private-env-canary"]}, "State": state,
                      "NetworkSettings": {"Networks": {"owned": {"IPAddress": h.ip, "NetworkID": h.network}}}}]
            return SimpleNamespace(stdout=json.dumps(value).encode())
        if command[:3] == ["docker", "network", "inspect"]:
            return SimpleNamespace(stdout=json.dumps([{"Internal": h.internal, "Labels": {Q.LABEL: check.token}}]).encode())
        assert command[0] == "npm"
        h.browser_calls += 1
        phase = kwargs["env"]["CSP_PHASE"]
        assert kwargs["env"]["CSP_EDGE_IP"] == h.ip
        (check.out / f"browser-{phase}.json").write_text(json.dumps(h.browser_summary))
        if h.on_browser:
            h.on_browser()
        return SimpleNamespace(returncode=h.browser_exit, stdout=b"password-canary", stderr=b"cookie-canary")

    def probe(address, context, hostname, path, role, *, deadline=None):
        assert address == h.ip and (hostname, path, role) in Q.EDGE_ORIGINS
        assert deadline is not None and deadline > h.clock
        h.probes.append((hostname, path, role))
        if h.on_probe:
            h.on_probe()
        return h.probe_results.get(role, "ready")

    check.compose = compose
    monkeypatch.setattr(Q, "run", command)
    monkeypatch.setattr(Q, "edge_probe", probe)
    return h


def test_loopback_health_never_substitutes_for_https_edge(edge_harness):
    h = edge_harness
    h.probe_results["web"] = "edge_http_unavailable"
    with pytest.raises(ValueError, match="^edge_http_unavailable$"):
        h.check.execute()
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["api_loopback_ready"] and evidence["web_loopback_ready"]
    assert evidence["attempts"] == 4 and not evidence["edge_web_ready"]
    assert h.browser_calls == 0 and h.check.summary["result"] == "FAIL"


@pytest.mark.parametrize("health", ["starting", "unhealthy", "unknown"])
def test_web_health_must_be_ready_even_if_http_responds(edge_harness, health):
    h = edge_harness
    h.health["web"] = health
    with pytest.raises(ValueError, match="^edge_http_unavailable$"):
        h.check.ready()
    assert not h.probes and h.browser_calls == 0
    assert not h.check.summary["edge_readiness"][0]["web_loopback_ready"]


@pytest.mark.parametrize("status", ["exited", "restarting", "paused"])
def test_caddy_must_be_running_before_any_https_probe(edge_harness, status):
    h = edge_harness
    h.caddy_status = status
    with pytest.raises(ValueError, match="^edge_http_unavailable$"):
        h.check.ready()
    assert not h.probes and h.browser_calls == 0


@pytest.mark.parametrize("fault", ["foreign", "malformed"])
def test_unsafe_or_malformed_inspect_is_refused_without_private_output(edge_harness, fault):
    h = edge_harness
    setattr(h, fault, True)
    with pytest.raises(ValueError, match="^edge_route_mismatch$"):
        h.check.ready()
    assert h.browser_calls == 0 and not h.probes
    assert "canary" not in json.dumps(h.check.summary)


def test_edge_must_be_on_owned_internal_network(edge_harness):
    h = edge_harness
    h.internal = False
    with pytest.raises(ValueError, match="^edge_route_mismatch$"):
        h.check.ready()
    assert not h.probes and h.browser_calls == 0


def test_unavailable_tls_ca_is_safe_and_never_launches_browser(edge_harness):
    h = edge_harness
    h.ca_bad = True
    with pytest.raises(ValueError, match="^edge_tls_unavailable$"):
        h.check.ready()
    assert not h.probes and h.browser_calls == 0
    assert "canary" not in json.dumps(h.check.summary)


@pytest.mark.parametrize("category", ["edge_tls_unavailable", "edge_route_mismatch", "edge_http_unavailable"])
def test_each_origin_must_pass_without_tls_or_route_fallback(edge_harness, category):
    h = edge_harness
    h.probe_results["api"] = category
    with pytest.raises(ValueError, match=f"^{category}$"):
        h.check.ready()
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["edge_web_ready"] and not evidence["edge_api_ready"]
    assert h.browser_calls == 0 and "canary" not in json.dumps(h.check.summary)


def test_recreated_edge_requires_two_observations_at_new_address(edge_harness):
    h = edge_harness
    def recreate():
        h.ip = "172.30.0.3"
        h.on_probe = None
    h.on_probe = recreate
    h.check.ready("after")
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["endpoint_changed"] and evidence["stable_observations"] == 2
    assert evidence["attempts"] == 3 and h.check._ready_edge[2] == h.ip
    assert h.check.browser("after") is True and h.browser_calls == 1


def test_initial_unavailability_is_polled_only_before_browser(edge_harness):
    h = edge_harness
    def first_failure():
        h.on_probe = None
        h.probe_results["web"] = "edge_http_unavailable"
    h.on_probe = first_failure
    original_sleep = Q.time.sleep
    def become_ready(seconds):
        original_sleep(seconds)
        h.probe_results.clear()
    Q.time.sleep = become_ready
    h.check.ready()
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["attempts"] == 3 and evidence["stable_observations"] == 2
    assert h.browser_calls == 0
    assert h.check.browser("before") is True and h.browser_calls == 1


def test_readiness_loss_resets_the_consecutive_observation_count(edge_harness, monkeypatch):
    h = edge_harness
    original_sleep = Q.time.sleep
    def alternate(seconds):
        original_sleep(seconds)
        h.probe_results["web"] = "edge_http_unavailable" if h.clock % 2 else "ready"
    monkeypatch.setattr(Q.time, "sleep", alternate)
    with pytest.raises(ValueError, match="^edge_http_unavailable$"):
        h.check.ready()
    assert h.check._ready_edge is None and h.browser_calls == 0


def test_deadline_cannot_be_passed_by_one_successful_observation(edge_harness, monkeypatch):
    h = edge_harness
    monkeypatch.setattr(Q, "READINESS_SECONDS", 1)
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.ready()
    assert h.check.summary["edge_readiness"][0]["attempts"] == 1
    assert h.check._ready_edge is None and h.browser_calls == 0


def test_both_https_origins_are_verified_before_browser_handoff(edge_harness):
    h = edge_harness
    h.check.ready("after")
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["last_failure"] == "none" and evidence["stable_observations"] == 2
    assert h.probes == list(Q.EDGE_ORIGINS) * 2 and h.browser_calls == 0
    assert h.check.browser("after") is True
    assert h.probes == list(Q.EDGE_ORIGINS) * 3 and h.browser_calls == 1
    assert h.check.summary["after_edge_stable_after_browser"] is True
    assert "canary" not in json.dumps(h.check.summary)


@pytest.mark.parametrize("change", ["address", "network", "unavailable"])
def test_handoff_refuses_changed_or_unavailable_edge_without_repolling(edge_harness, change):
    h = edge_harness
    h.check.ready("after")
    previous_probes = len(h.probes)
    if change == "address": h.ip = "172.30.0.3"
    elif change == "network": h.network = "replacement-network"
    else: h.probe_results["web"] = "edge_http_unavailable"
    with pytest.raises(ValueError, match="^edge_(not_stable|http_unavailable)$"):
        h.check.browser("after")
    assert h.browser_calls == 0 and len(h.probes) - previous_probes <= 2


def test_direct_browser_call_without_readiness_never_launches(edge_harness):
    h = edge_harness
    with pytest.raises(ValueError, match="^edge_not_stable$"):
        h.check.browser("after")
    assert h.browser_calls == 0 and not h.probes


@pytest.mark.parametrize("network_changed", [True, False])
def test_readiness_cannot_mask_single_browser_failure_or_trigger_retry(edge_harness, network_changed):
    h = edge_harness
    h.check.ready("after")
    h.browser_exit = 1
    h.browser_summary = {"passed": False, "diagnostics": {"events": [{
        "kind": "request_failed", "failure_category": "network_changed" if network_changed else "redacted",
    }]}}
    assert h.check.browser("after") is False
    assert h.browser_calls == 1 and h.check.summary["result"] == "FAIL"
    expected = "browser_network_changed" if network_changed else "browser_transport_unknown"
    assert h.check.summary["after_transport"] == expected
    assert "canary" not in json.dumps(h.check.summary)


def test_changed_edge_during_passing_browser_remains_a_failure(edge_harness):
    h = edge_harness
    h.check.ready("after")
    h.on_browser = lambda: setattr(h, "ip", "172.30.0.3")
    with pytest.raises(ValueError, match="^edge_not_stable$"):
        h.check.browser("after")
    assert h.browser_calls == 1 and h.check.summary["after_edge_stable_after_browser"] is False


def test_readiness_failure_is_retained_in_safe_final_summary(edge_harness, monkeypatch):
    h = edge_harness
    h.malformed = True
    h.check.prepare = lambda: setattr(h.check, "owns_output", True)
    h.check.cleanup = lambda: h.check.summary.update(cleanup="owned_project_only_PASS")
    monkeypatch.setattr(Q, "Check", lambda _args: h.check)
    monkeypatch.setattr(Q.argparse.ArgumentParser, "parse_args", lambda _self: args(h.check.out.parent))
    assert Q.main() == 1
    saved = json.loads((h.check.out / "summary.json").read_text())
    assert saved["result"] == "FAIL" and saved["failure_code"] == "edge_route_mismatch"
    assert saved["edge_readiness"][0]["attempts"] == 4
    assert saved["phase"] == "edge_readiness_before"
    assert saved["cleanup"] == "owned_project_only_PASS" and "canary" not in json.dumps(saved)
    assert h.browser_calls == 0


def test_hardened_readiness_failure_has_its_own_phase(edge_harness):
    h = edge_harness
    h.probe_results["api"] = "edge_tls_unavailable"
    with pytest.raises(ValueError, match="^edge_tls_unavailable$"):
        h.check.ready("after")
    assert h.check.summary["phase"] == "edge_readiness_after"
    assert h.check.summary["edge_readiness"][0]["phase"] == "after"
    assert h.browser_calls == 0


def test_actual_tls_context_trusts_only_disposable_ca_in_memory(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    # Synthetic CA/key never written to disk or diagnostics. Fixed scalar is
    # fixture material only; no real key or host trust-store mutation is involved.
    key = ec.derive_private_key(1, ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic.invalid")])
    ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
          .public_key(key.public_key()).serial_number(1)
          .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
          .not_valid_after(datetime(2100, 1, 1, tzinfo=timezone.utc))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
    check = Q.Check(args(tmp_path))
    check.compose = lambda *a, **k: SimpleNamespace(stdout=ca)
    context, identity = check.edge_context()
    assert context.check_hostname and context.verify_mode == Q.ssl.CERT_REQUIRED
    assert context.cert_store_stats()["x509_ca"] == 1
    assert identity == hashlib.sha256(ca).digest()
    assert not check.out.exists() and "synthetic.invalid" not in json.dumps(check.summary)




def test_loopback_commands_and_curl_share_remaining_budget(edge_harness):
    h = edge_harness
    old = h.check.compose
    calls = []
    def command(*args, **kw):
        calls.append((args, kw["timeout"]))
        result = old(*args, **kw)
        h.clock += .3
        return result
    h.check.compose = command
    with pytest.raises(Q.EdgeDeadlineExceeded):
        h.check.loopback_ready("web", deadline=.5)
    assert len(calls) == 2
    assert calls[0][1] == .5 and 0 < calls[1][1] <= .2
    assert "--max-time" in calls[0][0]
    assert float(calls[0][0][calls[0][0].index("--max-time") + 1]) == .5
    assert h.browser_calls == 0


def test_endpoint_change_survives_a_failed_poll(edge_harness, monkeypatch):
    h = edge_harness
    first = ("edge-A", "internal", "172.30.0.2", b"ca")
    second = ("edge-B", "internal", "172.30.0.3", b"ca")
    observations = iter([(first, None, "ready"), (None, None, "edge_http_unavailable"),
                         (second, None, "ready"), (second, None, "ready")])
    monkeypatch.setattr(h.check, "edge_round", lambda _evidence, **kw: next(observations))
    h.check.ready()
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["endpoint_changed"] is True and evidence["stable_observations"] == 2
    assert evidence["attempts"] == 4 and h.check._ready_edge == second
    assert "edge-A" not in json.dumps(h.check.summary) and "edge-B" not in json.dumps(h.check.summary)
    assert h.browser_calls == 0


def test_even_failed_replacement_probe_retains_observed_transition(edge_harness, monkeypatch):
    h = edge_harness
    original_sleep = Q.time.sleep
    def replace_then_fail(seconds):
        original_sleep(seconds)
        h.ip = "172.30.0.3"
        h.probe_results["web"] = "edge_http_unavailable"
    monkeypatch.setattr(Q.time, "sleep", replace_then_fail)
    with pytest.raises(ValueError, match="^edge_http_unavailable$"):
        h.check.ready()
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["endpoint_changed"] is True and evidence["stable_observations"] == 0
    assert h.check._ready_edge is None and h.browser_calls == 0
    assert "172.30.0.3" not in json.dumps(h.check.summary)


def test_handoff_deadline_failure_never_repolls_or_starts_browser(edge_harness):
    h = edge_harness
    h.check.ready("after")
    count = len(h.probes)
    h.probe_results["web"] = "edge_deadline_exceeded"
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.browser("after")
    assert len(h.probes) == count + 1 and h.browser_calls == 0
    assert h.check.summary["browser_edge_handoffs"][0]["last_failure"] == "edge_deadline_exceeded"


@pytest.mark.parametrize("at,allowed", [(89.999, True), (90, False), (91, False)])
def test_original_phase_deadline_controls_handoff(edge_harness, at, allowed):
    h = edge_harness
    h.check.ready("before")
    assert h.clock == 1 and h.check._phase_deadlines == {"before": 90}
    probes, commands = len(h.probes), len(h.commands)
    h.clock = at
    if allowed:
        assert h.check.browser("before") is True
        assert len(h.probes) == probes + 2 and h.browser_calls == 1
    else:
        with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
            h.check.browser("before")
        assert len(h.probes) == probes and len(h.commands) == commands
        assert h.browser_calls == 0
    assert h.check._phase_deadlines == {"before": 90}


def test_slow_handoff_metadata_cannot_open_another_probe(edge_harness, monkeypatch):
    h = edge_harness
    h.check.ready()
    count = len(h.probes)
    calls = []
    def consume(*, deadline):
        calls.append(deadline)
        h.clock = deadline
        return "owned-caddy", h.network, h.ip
    monkeypatch.setattr(h.check, "edge_binding", consume)
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.browser("before")
    assert calls == [90] and len(h.probes) == count and h.browser_calls == 0


def test_first_handoff_probe_consumes_original_budget(edge_harness):
    h = edge_harness
    h.check.ready()
    count, commands = len(h.probes), len(h.commands)
    h.on_probe = lambda: setattr(h, "clock", 90)
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.browser("before")
    assert len(h.probes) == count + 1 and h.browser_calls == 0
    # Initial identity/CA inspection only; no post-probe metadata operation.
    assert len(h.commands) == commands + 4


def test_final_launch_check_consumes_same_deadline(edge_harness, monkeypatch):
    h = edge_harness
    h.check.ready()
    original = h.check.browser_edge
    def handoff(phase):
        address = original(phase)
        h.clock = 90
        return address
    monkeypatch.setattr(h.check, "browser_edge", handoff)
    with pytest.raises(Q.EdgeDeadlineExceeded):
        h.check.browser("before")
    assert len(h.probes) == 6 and h.browser_calls == 0


def test_phase_budgets_are_separate_and_never_renewed(edge_harness):
    h = edge_harness
    h.check.ready("before")
    h.clock = 100
    h.check.ready("after")
    assert h.check._phase_deadlines == {"before": 90, "after": 190}
    calls = len(h.commands), len(h.probes)
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.browser("before")
    with pytest.raises(ValueError, match="^edge_not_stable$"):
        h.check.ready("before")
    assert (len(h.commands), len(h.probes)) == calls
    assert h.check.browser("after") is True and h.browser_calls == 1


def test_browser_failure_never_permits_same_phase_restart(edge_harness):
    h = edge_harness
    h.check.ready()
    h.browser_exit = 1
    h.on_browser = lambda: setattr(h, "clock", 200)
    assert h.check.browser("before") is False
    count = len(h.probes), len(h.commands)
    with pytest.raises(ValueError, match="^edge_not_stable$"):
        h.check.browser("before")
    with pytest.raises(ValueError, match="^edge_not_stable$"):
        h.check.ready("before")
    assert h.browser_calls == 1 and (len(h.probes), len(h.commands)) == count
    assert h.check._phase_deadlines == {"before": 90}


@pytest.mark.parametrize("replacement_count", [1, 3])
def test_endpoint_replacements_never_extend_phase(edge_harness, monkeypatch, replacement_count):
    h = edge_harness
    monkeypatch.setattr(Q, "READINESS_ATTEMPTS", 100)
    original_sleep = Q.time.sleep
    sleeps = []
    def replace(seconds):
        original_sleep(seconds)
        sleeps.append(seconds)
        if len(sleeps) <= replacement_count:
            h.ip = "172.30.0." + str(2 + len(sleeps))
        if len(sleeps) == replacement_count + 1:
            h.clock = 90
    monkeypatch.setattr(Q.time, "sleep", replace)
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.ready()
    assert h.check._phase_deadlines == {"before": 90} and h.browser_calls == 0
    evidence = h.check.summary["edge_readiness"][0]
    assert evidence["endpoint_changed"] and evidence["attempts"] == replacement_count + 1
    assert len(h.probes) == 2 * (replacement_count + 1)


def test_failed_poll_and_expiry_do_not_start_another_round(edge_harness, monkeypatch):
    h = edge_harness
    h.probe_results["web"] = "edge_http_unavailable"
    monkeypatch.setattr(Q.time, "sleep", lambda _s: setattr(h, "clock", 90))
    with pytest.raises(ValueError, match="^edge_deadline_exceeded$"):
        h.check.ready()
    assert len(h.probes) == 1 and h.browser_calls == 0
    assert h.check._phase_deadlines == {"before": 90}


def test_lifecycle_metadata_consumes_handoff_budget(edge_harness):
    h = edge_harness
    h.check.ready()
    original = h.check.compose
    calls = []
    def consume(*args, **kw):
        calls.append(kw["timeout"])
        result = original(*args, **kw)
        h.clock = 90
        return result
    h.check.compose = consume
    with pytest.raises(Q.EdgeDeadlineExceeded):
        h.check.lifecycle_snapshot("baseline_ready", deadline=h.check.phase_deadline("before"))
    assert calls == [8] and h.browser_calls == 0


# The sealed SIGALRM candidate retains its two failed guard-entry reproductions.
# These replacements test the stronger contract: no probe-owned signal state and
# explicit descriptor closure while a real KeyboardInterrupt traceback is alive.


@pytest.fixture
def wire_probe(monkeypatch):
    import errno
    h = SimpleNamespace(status=200, mime="text/html; charset=utf-8", body=b"<!DOCTYPE html><html></html>",
                        calls=[], hooks={}, tls_error=None, response_error=None, raw_response=None,
                        clock=0., fragment=16384, partial_send=16384, response_offset=0, input_bytes=0,
                        wire_input=None, eof_clean=True, connect_code=0, stall=None, advance=0.,
                        no_progress=None, raw_tail=b"", tcp_stall=False)
    def hook(stage):
        if stage in h.hooks: h.hooks[stage]()
    h.hook = hook
    class Raw:
        def __new__(cls):
            obj = object.__new__(cls); obj.closed = True; obj.opened = False
            h.raw = obj
            return obj
        def __init__(self, family, kind):
            assert (family, kind) == (Q.socket.AF_INET, Q.socket.SOCK_STREAM)
            self.closed, self.opened = False, True
            h.calls.append(("acquire",)); hook("acquire")
        def setblocking(self, value): assert value is False
        def connect_ex(self, destination):
            h.calls.append(("connect", destination)); hook("connect")
            return errno.EINPROGRESS if h.stall == "connect" else h.connect_code
        def getsockopt(self, *_): return 0
        def fileno(self): return -1 if self.closed else 19
        def send(self, data):
            hook("flush")
            if h.no_progress == "send": return 0
            count = min(len(data), h.partial_send)
            h.calls.append(("send", bytes(data[:count])))
            return count
        def recv(self, size):
            hook("receive")
            if h.stall in ("tls", "headers", "body") or h.tcp_stall:
                raise BlockingIOError
            # Positive fake peers explicitly model TCP EOF after TLS plaintext
            # is exhausted; a body boundary alone is no longer completion.
            if h.response_offset:
                data, h.raw_tail = h.raw_tail[:size], h.raw_tail[size:]
                return data
            return (h.wire_input or b"synthetic TLS record")[:size]
        def close(self):
            h.calls.append(("close",)); hook("close")
            self.closed = True
    class TLS:
        def do_handshake(self):
            hook("tls")
            if h.tls_error: raise h.tls_error
            if h.stall == "tls": raise Q.ssl.SSLWantReadError
        def selected_alpn_protocol(self): return None
        def pending(self): return 0
        def write(self, data):
            hook("request"); h.calls.append(("request", bytes(data)))
            outgoing.write(b"TLS request")
            return len(data)
        def read(self, size):
            content = h.raw_response
            if content is None:
                content = (f"HTTP/1.1 {h.status} Synthetic\r\nContent-Type: {h.mime}\r\n"
                           f"Content-Length: {len(h.body)}\r\n\r\n").encode() + h.body
            stage = "headers" if h.response_offset < content.index(b"\r\n\r\n") + 4 else "body"
            hook(stage)
            if h.response_error: raise h.response_error
            if h.stall == stage:
                raise Q.ssl.SSLWantReadError
            if h.no_progress == "tls_write": raise Q.ssl.SSLWantWriteError
            h.clock += h.advance
            data = content[h.response_offset:h.response_offset + min(size, h.fragment)]
            h.response_offset += len(data)
            if not data and not h.eof_clean: raise Q.ssl.SSLEOFError
            return data
    incoming, outgoing = Q.ssl.MemoryBIO(), Q.ssl.MemoryBIO()
    class Context:
        check_hostname = True
        verify_mode = Q.ssl.CERT_REQUIRED
        def wrap_bio(self, inp, out, *, server_side, server_hostname):
            nonlocal incoming, outgoing
            incoming, outgoing = inp, out
            assert server_side is False
            h.calls.append(("sni", server_hostname)); return TLS()
    class Poll:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def register(self, raw, event): assert raw is h.raw; h.calls.append(("poll", event))
        def select(self, timeout):
            assert 0 < timeout <= 2
            hook("poll"); h.clock += timeout
            return []
    h.context = Context()
    monkeypatch.setattr(Q.socket, "socket", Raw)
    monkeypatch.setattr(Q.socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("DNS forbidden"))
    monkeypatch.setattr(Q.selectors, "PollSelector", Poll)
    monkeypatch.setattr(Q.time, "monotonic", lambda: h.clock)
    return h


@pytest.mark.parametrize("origin", Q.EDGE_ORIGINS)
def test_signal_free_private_tcp_host_sni_and_single_request(wire_probe, monkeypatch, origin):
    h = wire_probe
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(key, "http://private-proxy-canary.invalid:9999")
    if origin[2] == "api": h.mime, h.body = "application/json", b'{"status":"ok"}'
    h.partial_send, h.fragment = 1, 1
    assert Q.edge_probe("172.30.0.2", h.context, *origin) == "ready"
    assert [x for x in h.calls if x[0] == "connect"] == [("connect", ("172.30.0.2", 443))]
    assert ("sni", origin[0]) in h.calls
    requests = [x[1] for x in h.calls if x[0] == "request"]
    assert requests == [(f"GET {origin[1]} HTTP/1.1\r\nHost: {origin[0]}\r\n"
                         "Connection: close\r\nAccept-Encoding: identity\r\n\r\n").encode()]
    assert h.raw.closed and len([x for x in h.calls if x[0] == "acquire"]) == 1


@pytest.mark.parametrize("status", [101, 301, 302, 307, 308, 401, 404, 502, 503])
def test_signal_free_status_refusal_has_no_retry(wire_probe, status):
    h = wire_probe; h.status = status
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == "edge_http_unavailable"
    assert len([x for x in h.calls if x[0] == "request"]) == 1 and h.raw.closed


@pytest.mark.parametrize("mime,body", [("application/json", b'{}'), ("text/html", b'canary'),
    ("text/plain", b'<!DOCTYPE html>')])
def test_signal_free_web_route_refusal(wire_probe, mime, body):
    h = wire_probe; h.mime, h.body = mime, body
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == "edge_route_mismatch"


@pytest.mark.parametrize("body", [b'{"status":"not_ready"}', b'[]', b'canary', b'x' * 5000])
def test_signal_free_api_body_refusal(wire_probe, body):
    h = wire_probe; h.mime, h.body = "application/json", body
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[1]) != "ready"
    assert h.raw.closed


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.1.1", "203.0.113.1", "8.8.8.8", "::1", "private.invalid"])
def test_signal_free_destination_refused_before_acquisition(wire_probe, address):
    h = wire_probe
    with pytest.raises(ValueError, match="^edge_route_mismatch$"):
        Q.edge_probe(address, h.context, *Q.EDGE_ORIGINS[0])
    assert not h.calls


def test_signal_free_path_and_verification_refused_before_acquisition(wire_probe):
    h = wire_probe
    with pytest.raises(ValueError, match="^edge_route_mismatch$"):
        Q.edge_probe("172.30.0.2", h.context, Q.EDGE_ORIGINS[0][0], "/private?canary", "web")
    for name, value in (("check_hostname", False), ("verify_mode", Q.ssl.CERT_NONE)):
        before = getattr(h.context, name); setattr(h.context, name, value)
        with pytest.raises(ValueError, match="^edge_tls_unavailable$"):
            Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0])
        setattr(h.context, name, before)
    assert not h.calls


@pytest.mark.parametrize("code,expected", [(62, "edge_route_mismatch"), (20, "edge_tls_unavailable")])
def test_signal_free_certificate_failure(wire_probe, code, expected):
    h = wire_probe
    error = Q.ssl.SSLCertVerificationError("private-certificate-canary"); error.verify_code = code
    h.tls_error = error
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == expected
    assert not any(x[0] == "request" for x in h.calls) and h.raw.closed


@pytest.mark.parametrize("stage", ["connect", "tls", "headers", "body"])
def test_signal_free_stall_consumes_absolute_budget(wire_probe, stage):
    h = wire_probe; h.stall = stage
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0], deadline=.03) == "edge_deadline_exceeded"
    assert h.clock == .03 and h.raw.closed
    assert len([x for x in h.calls if x[0] == "acquire"]) == 1


@pytest.mark.parametrize("stage", ["acquire", "connect", "tls", "flush", "headers", "body"])
def test_signal_free_each_stage_rechecks_deadline(wire_probe, stage):
    h = wire_probe; h.hooks[stage] = lambda: setattr(h, "clock", .1)
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0], deadline=.1) == "edge_deadline_exceeded"
    assert h.raw.closed


def test_signal_free_expired_phase_opens_no_socket(wire_probe):
    h = wire_probe
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0], deadline=0) == "edge_deadline_exceeded"
    assert not h.calls


def test_signal_free_slow_progress_never_renews_budget(wire_probe):
    h = wire_probe; h.advance, h.fragment = .03, 1
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == "edge_deadline_exceeded"
    assert 2 <= h.clock < 2.02 and h.raw.closed
    assert len([x for x in h.calls if x[0] == "request"]) == 1


@pytest.mark.parametrize("headers,body", [
    (b"Content-Length: 1\r\nContent-Length: 2\r\n", b'x'),
    (b"Content-Length: 1\r\nTransfer-Encoding: chunked\r\n", b'0\r\n\r\n'),
    (b"Content-Length: -1\r\n", b''), (b"Content-Length: +1\r\n", b'x'),
    (b"Transfer-Encoding: gzip\r\n", b''), (b"Content-Encoding: gzip\r\n", b''),
    (b"Upgrade: websocket\r\n", b''), (b"bad header\r\n", b''),
    (b" Folded: header\r\n", b''), (b"X-A: canary\x00\r\n", b''),
    (b"Content-Length: 3\r\n", b'x'),
    (b"Transfer-Encoding: chunked\r\n", b'-1\r\nx\r\n0\r\n\r\n'),
    (b"Transfer-Encoding: chunked\r\n", b'1\r\nxZZ0\r\n\r\n'),
    (b"Transfer-Encoding: chunked\r\n", b'0\r\nPrivate: canary\r\n\r\n'),
    (b"Transfer-Encoding: chunked\r\n", b'1;ext=x\r\nx\r\n0\r\n\r\n'),
    (b"Transfer-Encoding: chunked\r\n", b'1\r\nx\r\n'),
    (b"X-Long: " + b'x' * 16384 + b'\r\n', b''),
])
def test_signal_free_strict_http_framing(wire_probe, headers, body):
    h = wire_probe
    h.raw_response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n' + headers + b'\r\n' + body
    result = Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0])
    assert result == "edge_http_unavailable" and h.raw.closed and "canary" not in result


@pytest.mark.parametrize("chunked", [False, True])
def test_signal_free_fragmented_complete_body(wire_probe, chunked):
    h = wire_probe; h.fragment = 1
    body = b'<!DOCTYPE html><html>synthetic</html>'
    frame = (b'Transfer-Encoding: chunked\r\n\r\n' + f'{len(body):x}\r\n'.encode() + body + b'\r\n0\r\n\r\n'
             if chunked else f'Content-Length: {len(body)}\r\n\r\n'.encode() + body)
    h.raw_response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n' + frame
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == "ready" and h.raw.closed


@pytest.mark.parametrize("clean", [False, True])
def test_signal_free_close_delimited_needs_authenticated_tls_eof(wire_probe, clean):
    h = wire_probe; h.eof_clean = clean
    h.raw_response = b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html>'
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == ("ready" if clean else "edge_tls_unavailable")
    assert h.raw.closed


@pytest.mark.parametrize("size,ready", [(4096, True), (4097, True), (256 * 1024, True), (256 * 1024 + 1, False)])
def test_signal_free_html_limit_distinct_from_api(wire_probe, size, ready):
    h = wire_probe; h.body = b'<!DOCTYPE html>' + b'x' * (size - 15)
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == ("ready" if ready else "edge_http_unavailable")
    assert h.raw.closed


@pytest.mark.parametrize("size,ready", [(4096, True), (4097, False)])
def test_signal_free_exact_api_limit(wire_probe, size, ready):
    h = wire_probe; h.mime = "application/json"; h.body = b'{"status":"ok"}' + b' ' * (size - 15)
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[1]) == ("ready" if ready else "edge_http_unavailable")


@pytest.mark.parametrize("kind", ["send", "tls_write"])
def test_signal_free_impossible_progress_is_refused(wire_probe, kind):
    h = wire_probe; h.no_progress = kind
    assert Q.edge_probe("172.30.0.2", h.context, *Q.EDGE_ORIGINS[0]) == "edge_http_unavailable" and h.raw.closed


def test_signal_free_wire_and_bio_limits(wire_probe):
    h = wire_probe
    transport = Q._EdgeTransport(h.context, Q.EDGE_ORIGINS[0][0], 2)
    transport.wire = Q.WIRE_LIMIT
    with pytest.raises(ValueError, match="^edge_http_unavailable$"): transport.receive()
    transport.incoming.write(b'x' * (Q.BIO_LIMIT + 1))
    with pytest.raises(ValueError, match="^edge_http_unavailable$"): transport.check()
    transport.close()


def test_signal_free_does_not_read_or_write_global_signal_state(wire_probe, monkeypatch):
    import signal
    def forbidden(*_a, **_k): pytest.fail("probe accessed process signal state")
    for name in ("signal", "getsignal", "setitimer", "getitimer", "pthread_sigmask", "sigpending"):
        monkeypatch.setattr(signal, name, forbidden)
    assert Q.edge_probe("172.30.0.2", wire_probe.context, *Q.EDGE_ORIGINS[0]) == "ready"


def _signal_free_interrupt_child(point):
    """Actual descriptors and actual SIGINT; no peer, worker or external network."""
    import errno
    import inspect
    import os
    import signal
    import socket
    import sys
    import threading
    import time
    from unittest.mock import patch

    real_socket = socket.socket
    sockets, descriptors, sent, events = [], [], [], []
    unrelated = real_socket(socket.AF_INET, socket.SOCK_STREAM)
    before_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    previous = signal.getsignal(signal.SIGALRM)
    before_threads = threading.enumerate()
    assert signal.getitimer(signal.ITIMER_REAL) == (0., 0.)
    def foreign(_sig, _frame): events.append(True)
    signal.signal(signal.SIGALRM, foreign)
    signal.setitimer(signal.ITIMER_REAL, 20)
    def interrupt(label):
        if label == point and not sent:
            sent.append(label)
            signal.raise_signal(signal.SIGINT)
    body = b'<!DOCTYPE html>'
    content = f'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body
    class Raw(real_socket):
        def __init__(self, family, kind):
            real_socket.__init__(self, family, kind)
            sockets.append(self)
            descriptors.append(self.fileno())
            interrupt('during_acquisition')
        def connect_ex(self, _address): interrupt('connect'); return 0
        def recv(self, _size): return b''
        def send(self, data): interrupt('flush'); return len(data)
        def close(self):
            interrupt('during_cleanup')
            real_socket.close(self)
    class TLS:
        offset = 0
        def do_handshake(self): interrupt('tls')
        def selected_alpn_protocol(self): return None
        def pending(self): return 0
        def write(self, data): outgoing.write(b'fixture'); return len(data)
        def read(self, size):
            interrupt('headers' if self.offset < content.index(b'\r\n\r\n') + 4 else 'body')
            data = content[self.offset:self.offset + size]; self.offset += len(data)
            return data
    class Context:
        check_hostname, verify_mode = True, Q.ssl.CERT_REQUIRED
        def wrap_bio(self, _incoming, out, **_kw):
            nonlocal outgoing
            outgoing = out
            return TLS()
    outgoing = None
    connect_lines, start = inspect.getsourcelines(Q._EdgeTransport.connect)
    acquire_line = start + next(i for i, line in enumerate(connect_lines) if 'socket.socket.__init__' in line)
    probe_lines, start = inspect.getsourcelines(Q.edge_probe)
    closes = [start + i for i, line in enumerate(probe_lines) if line.strip() == 'transport.close()']
    def trace(frame, event, _arg):
        if frame.f_code is Q._EdgeTransport.connect.__code__ and event == 'line':
            if frame.f_lineno == acquire_line: interrupt('before_acquisition')
            if frame.f_lineno == acquire_line + 1: interrupt('after_acquisition')
        if frame.f_code is Q.edge_probe.__code__ and event == 'line':
            if frame.f_lineno == closes[0]: interrupt('before_cleanup')
            if frame.f_lineno == closes[1]: interrupt('after_cleanup')
        if frame.f_code is Q._EdgeTransport.close.__code__ and event == 'call': interrupt('cleanup_entry')
        return trace
    caught = None
    try:
        with patch.object(Q.socket, 'socket', Raw):
            sys.settrace(trace)
            try:
                interrupt('before_entry')
                Q.edge_probe('172.30.0.2', Context(), *Q.EDGE_ORIGINS[0], deadline=time.monotonic()+2)
            except KeyboardInterrupt as error:
                caught = error  # Keep both exception and traceback LIVE for FD checks.
            finally:
                sys.settrace(None)
        assert caught is not None and caught.__traceback__ is not None and len(sent) == 1
        assert all(raw.fileno() == -1 for raw in sockets), 'owned descriptor survived cancellation'
        for fd in descriptors:
            try:
                os.fstat(fd)
            except OSError as error:
                assert error.errno == errno.EBADF
            else:
                raise AssertionError('closed descriptor remained open at OS boundary')
        assert unrelated.fileno() >= 0
        os.fstat(unrelated.fileno())
        assert signal.getsignal(signal.SIGALRM) is foreign
        timer = signal.getitimer(signal.ITIMER_REAL)
        assert 15 < timer[0] <= 20 and timer[1] == 0
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == before_mask
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
        assert threading.enumerate() == before_threads
        signal.raise_signal(signal.SIGALRM)
        assert events == [True]
        return {'point':point, 'SIGINT_count':len(sent), 'traceback_retained':True,
                'all_owned_descriptors_closed':True, 'foreign_signal_state_unchanged':True,
                'no_background_worker':True, 'subsequent_foreign_signal_functional':True}
    finally:
        sys.settrace(None)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        # Fixture cleanup is after the result assertions, never their evidence.
        for raw in sockets: real_socket.close(raw)
        unrelated.close()


@pytest.mark.parametrize('point', ['before_entry', 'before_acquisition', 'during_acquisition',
    'after_acquisition', 'connect', 'tls', 'flush', 'headers', 'body', 'before_cleanup',
    'cleanup_entry', 'during_cleanup', 'after_cleanup'])
def test_signal_free_actual_SIGINT_closes_descriptor_with_traceback_alive(point):
    import os
    import subprocess
    import sys
    code = ("import json,runpy,sys; m=runpy.run_path(sys.argv[1]); "
            "print(json.dumps(m['_signal_free_interrupt_child'](sys.argv[2]),sort_keys=True))")
    result = subprocess.run([sys.executable, '-B', '-c', code, __file__, point],
                            capture_output=True, timeout=10, env=dict(os.environ))
    assert result.returncode == 0, 'native cancellation fixture failed: ' + result.stderr.decode()[-1500:]
    evidence = json.loads(result.stdout)
    assert evidence['point'] == point and evidence['SIGINT_count'] == 1
    assert all(evidence[name] for name in ('traceback_retained', 'all_owned_descriptors_closed',
        'foreign_signal_state_unchanged', 'no_background_worker', 'subsequent_foreign_signal_functional'))


@pytest.fixture
def memory_tls_peer(tmp_path, monkeypatch):
    """Real OpenSSL in both directions, synthetic CA and zero network dispatch."""
    import socket
    from datetime import datetime, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.derive_private_key(17, ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic-csp-fixture')])
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
               .public_key(key.public_key())
               .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
               .not_valid_after(datetime(2100, 1, 1, tzinfo=timezone.utc)))
    ca = (builder.serial_number(17).add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .sign(key, hashes.SHA256()))
    leaf_key = ec.derive_private_key(19, ec.SECP256R1())
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, Q.EDGE_ORIGINS[0][0])]))
            .issuer_name(subject).public_key(leaf_key.public_key()).serial_number(18)
            .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
            .not_valid_after(datetime(2100, 1, 1, tzinfo=timezone.utc)))
    cert = (leaf.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(x[0]) for x in Q.EDGE_ORIGINS]), critical=False)
            .sign(key, hashes.SHA256()))
    certfile, keyfile = tmp_path/'fixture-cert.pem', tmp_path/'fixture-key.pem'
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    keyfile.chmod(0o600)
    h = SimpleNamespace(sni=[], requests=[], destinations=[], opened=[], fragment=17,
                        body=b'<!DOCTYPE html><html>fixture</html>', mime='text/html', abrupt=False,
                        response=None, server_hostname=None, client_context=None, raw_tail=b'', tcp_stall=False, coalesced_tail=False, response_tail=b'')
    server_context = Q.ssl.SSLContext(Q.ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(certfile, keyfile)
    server_context.set_alpn_protocols(['http/1.1'])
    server_context.set_servername_callback(lambda _s, name, _c: h.sni.append(name))
    h.context = Q.ssl.SSLContext(Q.ssl.PROTOCOL_TLS_CLIENT)
    h.context.load_verify_locations(cadata=ca.public_bytes(serialization.Encoding.PEM).decode())
    h.context.set_alpn_protocols(['http/1.1'])
    h.server_context = server_context
    real_socket = socket.socket
    class Raw(real_socket):
        def __init__(self, family, kind):
            real_socket.__init__(self, family, kind); h.opened.append(self)
            self.inp, self.out = Q.ssl.MemoryBIO(), Q.ssl.MemoryBIO()
            self.server = server_context.wrap_bio(self.inp, self.out, server_side=True)
            self.handshake, self.responded, self.request = False, False, bytearray()
        def connect_ex(self, address): h.destinations.append(address); return 0
        def send(self, data):
            count = min(len(data), h.fragment)
            self.inp.write(bytes(data[:count]))
            try:
                if not self.handshake:
                    self.server.do_handshake(); self.handshake = True
                while not self.responded:
                    self.request.extend(self.server.read(4096))
                    if b'\r\n\r\n' in self.request:
                        h.requests.append(bytes(self.request))
                        response = h.response
                        if response is None:
                            response = (f'HTTP/1.1 200 OK\r\nContent-Type: {h.mime}\r\n'
                                        f'Content-Length: {len(h.body)}\r\n\r\n').encode() + h.body
                        self.server.write(response)
                        if h.response_tail: self.server.write(h.response_tail)
                        self.responded = True
                        if not h.abrupt:
                            try: self.server.unwrap()
                            except Q.ssl.SSLWantReadError: pass
            except Q.ssl.SSLWantReadError:
                pass
            return count
        def recv(self, size):
            if self.out.pending:
                data = self.out.read(min(size, h.fragment))
                if self.responded and h.coalesced_tail and not self.out.pending and len(data) < size:
                    count = size - len(data)
                    data += h.raw_tail[:count]; h.raw_tail = h.raw_tail[count:]
                return data
            if self.responded:
                if h.tcp_stall: raise BlockingIOError
                data, h.raw_tail = h.raw_tail[:size], h.raw_tail[size:]
                return data
            raise BlockingIOError
    monkeypatch.setattr(Q.socket, 'socket', Raw)
    monkeypatch.setattr(Q.socket, 'getaddrinfo', lambda *_a, **_k: pytest.fail('DNS forbidden'))
    return h


@pytest.mark.parametrize('origin', Q.EDGE_ORIGINS)
def test_signal_free_real_openssl_fragmented_handshake_and_http(memory_tls_peer, origin):
    h = memory_tls_peer
    if origin[2] == 'api': h.mime, h.body = 'application/json', b'{"status":"ok"}'
    assert Q.edge_probe('172.30.0.2', h.context, *origin) == 'ready'
    assert h.sni == [origin[0]] and h.destinations == [('172.30.0.2', 443)]
    assert len(h.requests) == 1 and f'Host: {origin[0]}\r\n'.encode() in h.requests[0]
    assert all(raw.fileno() == -1 for raw in h.opened)


def test_signal_free_real_openssl_wrong_ca(memory_tls_peer):
    h = memory_tls_peer
    context = Q.ssl.SSLContext(Q.ssl.PROTOCOL_TLS_CLIENT)
    assert context.cert_store_stats()['x509_ca'] == 0
    assert Q.edge_probe('172.30.0.2', context, *Q.EDGE_ORIGINS[0]) == 'edge_tls_unavailable'
    assert h.requests == [] and all(raw.fileno() == -1 for raw in h.opened)


def test_signal_free_real_openssl_name_mismatch(memory_tls_peer, monkeypatch):
    h = memory_tls_peer
    # TLS name failure is real, with the route allowlist synthetic only in test.
    monkeypatch.setattr(Q, 'EDGE_ORIGINS', (('wrong.fixture.invalid', '/sign-in', 'web'),))
    assert Q.edge_probe('172.30.0.2', h.context, *Q.EDGE_ORIGINS[0]) == 'edge_route_mismatch'
    assert h.sni == ['wrong.fixture.invalid'] and h.requests == []
    assert all(raw.fileno() == -1 for raw in h.opened)


@pytest.mark.parametrize('abrupt', [True, False])
def test_signal_free_real_openssl_close_delimited_authentication(memory_tls_peer, abrupt):
    h = memory_tls_peer; h.abrupt = abrupt
    h.response = b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html>'
    assert Q.edge_probe('172.30.0.2', h.context, *Q.EDGE_ORIGINS[0]) == ('edge_tls_unavailable' if abrupt else 'ready')
    assert all(raw.fileno() == -1 for raw in h.opened)


def test_signal_free_real_openssl_incomplete_framing(memory_tls_peer):
    h = memory_tls_peer
    h.response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 200\r\n\r\n<!DOCTYPE html>'
    assert Q.edge_probe('172.30.0.2', h.context, *Q.EDGE_ORIGINS[0]) == 'edge_http_unavailable'
    assert all(raw.fileno() == -1 for raw in h.opened)


@pytest.mark.parametrize('which', ['incoming', 'outgoing'])
@pytest.mark.parametrize('extra', [0, 1])
def test_signal_free_pending_bio_boundary(wire_probe, which, extra):
    h = wire_probe; t = Q._EdgeTransport(h.context, Q.EDGE_ORIGINS[0][0], 2)
    getattr(t, which).write(b'x' * (Q.BIO_LIMIT + extra))
    if extra:
        with pytest.raises(ValueError, match='^edge_http_unavailable$'): t.check()
    else:
        t.check()
    t.close()


def test_signal_free_wire_ceiling_prevents_extra_transmission(wire_probe):
    h = wire_probe; t = Q._EdgeTransport(h.context, Q.EDGE_ORIGINS[0][0], 2)
    t.connect('172.30.0.2')
    try:
        t.wire = Q.WIRE_LIMIT - 1; t.outgoing.write(b'x'); t.flush()
        assert t.wire == Q.WIRE_LIMIT
        count = len([x for x in h.calls if x[0] == 'send'])
        t.outgoing.write(b'x')
        with pytest.raises(ValueError, match='^edge_http_unavailable$'): t.flush()
        assert len([x for x in h.calls if x[0] == 'send']) == count
        with pytest.raises(ValueError, match='^edge_http_unavailable$'): t.receive()
    finally:
        t.close()


def test_signal_free_cumulative_chunk_metadata_bounded(wire_probe):
    h = wire_probe
    chunks = b'1\r\nx\r\n' * 4000  # Body is small; cumulative framing exceeds 16 KiB.
    h.raw_response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nTransfer-Encoding: chunked\r\n\r\n' + chunks + b'0\r\n\r\n'
    assert Q.edge_probe('172.30.0.2', h.context, *Q.EDGE_ORIGINS[0]) == 'edge_http_unavailable'
    assert h.raw.closed


def test_signal_free_native_poll_owns_no_descriptor():
    import socket
    import time
    # Unconnected socket only: no bind, listen, DNS or outbound connect. Native
    # poll must time out or report local readiness without creating another FD.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw:
        raw.setblocking(False)
        t = object.__new__(Q._EdgeTransport)
        t.raw, t.deadline = raw, time.monotonic() + .1
        t.incoming, t.outgoing = Q.ssl.MemoryBIO(), Q.ssl.MemoryBIO()
        started = time.monotonic()
        try:
            t.wait(Q.selectors.EVENT_WRITE)
        except Q.EdgeDeadlineExceeded:
            assert time.monotonic() - started < .5
        assert raw.fileno() >= 0
    assert raw.fileno() == -1


@pytest.mark.parametrize('version,mode', [('1.0','length'), ('1.0','close'),
                                         ('1.1','length'), ('1.1','chunked')])
def test_complete_single_response_preserves_valid_protocols(memory_tls_peer, version, mode):
    h = memory_tls_peer; body = b'<!DOCTYPE html>'
    if mode == 'chunked':
        framing = b'Transfer-Encoding: chunked\r\n\r\nf\r\n'+body+b'\r\n0\r\n\r\n'
    elif mode == 'length':
        framing = b'Content-Length: 15\r\n\r\n'+body
    else:
        framing = b'\r\n'+body
    h.response = f'HTTP/{version} 200 OK\r\nContent-Type: text/html\r\n'.encode()+framing
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0]) == 'ready'
    assert len(h.requests) == 1 and all(raw.fileno() == -1 for raw in h.opened)


@pytest.mark.parametrize('coding', ['chunked','identity','gzip'])
def test_http10_any_transfer_encoding_refused_before_body(wire_probe,coding):
    h = wire_probe
    h.raw_response = f'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nTransfer-Encoding: {coding}\r\n\r\nf\r\n<!DOCTYPE html>\r\n0\r\n\r\n'.encode()
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0]) == 'edge_http_unavailable'
    assert h.response_offset == h.raw_response.index(b'\r\n\r\n') + 4
    assert h.raw.closed


def test_http10_chunked_refused_through_actual_openssl(memory_tls_peer):
    h = memory_tls_peer
    h.response = b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nTransfer-Encoding: chunked\r\n\r\nf\r\n<!DOCTYPE html>\r\n0\r\n\r\n'
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0]) == 'edge_http_unavailable'
    assert all(raw.fileno() == -1 for raw in h.opened)


@pytest.mark.parametrize('mode',['length','chunked'])
def test_trailing_plaintext_refused_through_plaintext_adapter(wire_probe,mode):
    h = wire_probe
    framing = (b'Content-Length: 15\r\n\r\n<!DOCTYPE html>' if mode=='length' else
               b'Transfer-Encoding: chunked\r\n\r\nf\r\n<!DOCTYPE html>\r\n0\r\n\r\n')
    h.raw_response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n'+framing+b'HTTP/1.1 503 Fault\r\n\r\nprivate-canary'
    result = Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0])
    assert result == 'edge_http_unavailable' and h.raw.closed
    assert h.response_offset < len(h.raw_response) and 'canary' not in result


@pytest.mark.parametrize('mode',['length','chunked'])
@pytest.mark.parametrize('fragment',[1,16384])
def test_trailing_plaintext_refused_through_real_openssl(memory_tls_peer,mode,fragment):
    h = memory_tls_peer; h.fragment=fragment
    framing = (b'Content-Length: 15\r\n\r\n<!DOCTYPE html>' if mode=='length' else
               b'Transfer-Encoding: chunked\r\n\r\nf\r\n<!DOCTYPE html>\r\n0\r\n\r\n')
    h.response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n'+framing+b'HTTP/1.1 503 Fault\r\n\r\nprivate-canary'
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0]) == 'edge_http_unavailable'
    assert len(h.requests) == 1 and all(raw.fileno() == -1 for raw in h.opened)


@pytest.mark.parametrize('role', ['api','web'])
def test_fixed_length_without_tls_close_notify_is_not_complete(memory_tls_peer,role):
    h = memory_tls_peer; h.abrupt=True
    if role=='api':h.mime,h.body='application/json',b'{"status":"ok"}'
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[role=='api']) == 'edge_tls_unavailable'
    assert all(raw.fileno() == -1 for raw in h.opened)


def test_post_close_transport_bytes_are_refused(memory_tls_peer):
    h = memory_tls_peer;h.raw_tail=b'synthetic-extra-record'
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0]) == 'edge_http_unavailable'
    assert all(raw.fileno() == -1 for raw in h.opened)


@pytest.mark.parametrize('boundary', ['tls','tcp'])
def test_completion_stall_consumes_same_absolute_deadline(wire_probe,boundary):
    h = wire_probe
    if boundary=='tls':
        def hold_after_body():
            if h.response_offset >= len(h.raw_response):raise Q.ssl.SSLWantReadError
        h.raw_response=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 15\r\n\r\n<!DOCTYPE html>'
        h.hooks['body']=hold_after_body;h.tcp_stall=True
    else:h.tcp_stall=True
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0],deadline=.1) == 'edge_deadline_exceeded'
    assert h.clock == .1 and h.raw.closed
    assert len([c for c in h.calls if c[0]=='request'])==1


@pytest.mark.parametrize('buffer',['tls','incoming','outgoing','tcp'])
def test_completion_refuses_residual_buffers(buffer):
    class FakeBIO:
        pending=0
        eof=True
    incoming,outgoing=FakeBIO(),FakeBIO()
    if buffer=='incoming':incoming.pending=1
    if buffer=='outgoing':outgoing.pending=1
    t=SimpleNamespace(check=lambda:None,read=lambda _n:b'',clean_eof=True,
        tls=SimpleNamespace(pending=lambda:1 if buffer=='tls' else 0),
        incoming=incoming,outgoing=outgoing,receive=lambda:buffer=='tcp')
    if buffer=='tcp':incoming.eof=False
    with pytest.raises(ValueError,match='^edge_http_unavailable$'):
        Q._EdgeTransport.finish_response(t)


def test_post_close_bytes_coalesced_in_memorybio_are_refused(memory_tls_peer):
    h=memory_tls_peer;h.fragment=16384;h.coalesced_tail=True;h.raw_tail=b'extra-after-close'
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0])=='edge_http_unavailable'
    assert all(raw.fileno()==-1 for raw in h.opened)


def test_trailing_plaintext_in_later_tls_record_is_refused(memory_tls_peer):
    h=memory_tls_peer;h.response_tail=b'late-plaintext-canary'
    assert Q.edge_probe('172.30.0.2',h.context,*Q.EDGE_ORIGINS[0])=='edge_http_unavailable'
    assert all(raw.fileno()==-1 for raw in h.opened)
