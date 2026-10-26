"""Disposable CSP harness safeguards; no Docker, database or development stores."""

from argparse import Namespace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
import pytest
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
