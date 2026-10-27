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
            )
        ):
            assert line in local
    for line in source.splitlines():
        if line.lstrip().startswith("#"):
            assert line in local
    assert "tls internal" in local
    assert "auto_https disable_redirects" in local


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


def test_all_existing_browser_security_assertions_are_preserved():
    source = (Q.ROOT / "frontend/csp/hydration.spec.ts").read_text()
    assertions = "\n".join(
        line.strip()
        for line in source.splitlines()
        if "expect(" in line or "expect.poll(" in line
    )
    # Reviewed baseline 291eb523: CSP, auth/cookies, nonce/spoof, negative payloads,
    # zero browser errors, external-call refusal and complete logout/revocation.
    assert hashlib.sha256(assertions.encode()).hexdigest() == (
        "74b14cef28c83c9020830613dcff7766beb4689f8b6a7b1fb05fb90a5517ae98"
    )
    assert 'retries: 0' in (Q.ROOT / "frontend/csp/playwright.config.ts").read_text()


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
