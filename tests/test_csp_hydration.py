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
