"""Conformance suite for the prompt asset contract (package 01B0).

01B (migration of production prompts) and 06C (per-language behaviour) must keep these
passing. The suite uses only the non-production fixture tree and temp copies of it.
"""

from __future__ import annotations

import hashlib
import shutil
import socket
from pathlib import Path

import pytest

from src.prompt_loader import (
    FilePromptLoader,
    IncompatiblePrompt,
    InvalidPromptAsset,
    MissingPromptVersion,
    PromptLoader,
    VariableMismatch,
    compute_sha256,
    parse_asset,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "prompts"


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    dest = tmp_path / "prompts"
    shutil.copytree(FIXTURES, dest)
    return dest


@pytest.fixture()
def loader() -> FilePromptLoader:
    return FilePromptLoader(FIXTURES)


def _asset_text(**overrides: str) -> str:
    meta = {
        "id": "x", "family": "demo/x", "version": "1.0.0", "variables": "[a]",
        "compatible_with": "[c1]", "description": "d",
    }
    meta.update(overrides)
    body = meta.pop("_body", "hi {a}\n")
    front = "\n".join(f"{k}: {v}" for k, v in meta.items() if v is not None)
    return f"---\n{front}\n---\n{body}"


def test_loader_satisfies_protocol(loader):
    assert isinstance(loader, PromptLoader)


def test_schema_fields_parse(loader):
    asset = loader.get("demo/greeting", "1.1.0")
    assert asset.id == "demo-greeting"
    assert asset.variables == ("name", "topic")
    assert asset.compatible_with == ("fixture-consumer-v1", "fixture-consumer-v2")
    assert asset.status == "approved"
    dep = loader.get("demo/farewell", "2.0.0")
    assert dep.status == "deprecated" and dep.rollback_to == "1.0.0" and dep.deprecated_reason


@pytest.mark.parametrize("bad", [
    _asset_text(id=None),
    _asset_text(version="v1"),
    _asset_text(version="1.0"),
    _asset_text(family="nofolder"),
    _asset_text(status="live"),
    _asset_text(status="deprecated"),  # needs deprecated_reason
    _asset_text(variables="a"),
    _asset_text(compatible_with="[]"),
    _asset_text(sha256="abc"),
    _asset_text(surprise="1"),
    "no front matter\n",
    "---\nid: x\n",
])
def test_invalid_schema_rejected(bad):
    with pytest.raises(InvalidPromptAsset):
        parse_asset(bad)


def test_semantic_version_ordering_is_numeric(loader):
    assert loader.versions("demo/greeting") == ["1.0.0", "1.1.0", "1.10.0"]


def test_version_and_hash_are_independent(loader, tree):
    a = loader.get("demo/greeting", "1.0.0")
    assert a.sha256 == hashlib.sha256(a.body.encode("utf-8")).hexdigest()
    # Same body, different declared version: different version, identical hash.
    text = (tree / "demo" / "greeting.v1.0.0.md").read_text(encoding="utf-8")
    twin = parse_asset(text.replace("version: 1.0.0", "version: 1.0.1"))
    assert twin.version != a.version and twin.sha256 == a.sha256
    # Changed body, same version: hash changes, version is untouched.
    edited = parse_asset(text.replace("greeting one", "greeting uno"))
    assert edited.version == a.version and edited.sha256 != a.sha256


def test_render_matches_str_format(loader):
    asset = loader.get("demo/greeting", "1.1.0")
    out = loader.render(asset, {"name": "Ada", "topic": "Ask4Mo"})
    assert out == asset.body.format(name="Ada", topic="Ask4Mo")
    assert "{ok}" in out


def test_render_missing_variable(loader):
    with pytest.raises(VariableMismatch, match="topic"):
        loader.render(loader.get("demo/greeting", "1.1.0"), {"name": "Ada"})


def test_render_extra_and_unknown_variable(loader):
    with pytest.raises(VariableMismatch, match="extra"):
        loader.render(loader.get("demo/greeting", "1.0.0"), {"name": "Ada", "extra": "x"})


def test_undeclared_body_placeholder_rejected():
    with pytest.raises(InvalidPromptAsset, match="undeclared"):
        parse_asset(_asset_text(_body="hi {a} {b}\n"))


def test_declared_but_unused_variable_rejected():
    with pytest.raises(InvalidPromptAsset, match="unused"):
        parse_asset(_asset_text(variables="[a, b]"))


@pytest.mark.parametrize("body", ["{a.__class__}\n", "{a[0]}\n", "{a!r}\n", "{a:>5}\n", "{}\n", "{a\n"])
def test_unsafe_placeholder_forms_rejected(body):
    with pytest.raises(InvalidPromptAsset):
        parse_asset(_asset_text(_body=body))


def test_missing_version_and_family(loader):
    with pytest.raises(MissingPromptVersion):
        loader.resolve("demo/greeting", "9.9.9")
    with pytest.raises(MissingPromptVersion):
        loader.resolve("demo/nothing")
    with pytest.raises(MissingPromptVersion):
        FilePromptLoader(FIXTURES / "does-not-exist")


def test_default_is_pointer_not_highest(loader):
    # 1.10.0 is a draft; the pointer names 1.1.0 explicitly.
    assert loader.resolve("demo/greeting").version == "1.1.0"
    assert loader.resolve("demo/farewell").version == "1.0.0"  # 2.0.0 exists but is deprecated


def test_draft_never_resolves(loader):
    with pytest.raises(MissingPromptVersion, match="draft"):
        loader.resolve("demo/greeting", "1.10.0")


def test_without_pointer_highest_approved_is_current(tree):
    (tree / "current.json").unlink()
    ld = FilePromptLoader(tree)
    assert ld.resolve("demo/greeting").version == "1.1.0"  # draft 1.10.0 skipped


def test_rollback_by_pointer_without_code_change(tree):
    assert FilePromptLoader(tree).resolve("demo/greeting").version == "1.1.0"
    (tree / "current.json").write_text('{"demo/greeting": "1.0.0"}', encoding="utf-8")
    rolled = FilePromptLoader(tree)
    asset = rolled.resolve("demo/greeting")
    assert asset.version == "1.0.0"
    assert rolled.render(asset, {"name": "Ada"}) == "Hello Ada, this is greeting one.\n"


def test_pointer_to_missing_version_or_family_is_refused(tree):
    (tree / "current.json").write_text('{"demo/greeting": "7.0.0"}', encoding="utf-8")
    with pytest.raises(MissingPromptVersion):
        FilePromptLoader(tree).resolve("demo/greeting")
    (tree / "current.json").write_text('{"demo/ghost": "1.0.0"}', encoding="utf-8")
    with pytest.raises(MissingPromptVersion):
        FilePromptLoader(tree)


def test_recorded_hash_matches_is_accepted(tree):
    path = tree / "demo" / "greeting.v1.0.0.md"
    body = path.read_text(encoding="utf-8").split("---\n", 2)[2]
    path.write_text(path.read_text(encoding="utf-8").replace(
        "status: approved", f"status: approved\nsha256: {compute_sha256(body)}"), encoding="utf-8")
    assert FilePromptLoader(tree).get("demo/greeting", "1.0.0").recorded_sha256


def test_integrity_hash_mismatch_refused(tree):
    path = tree / "demo" / "greeting.v1.0.0.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "status: approved", "status: approved\nsha256: " + "0" * 64), encoding="utf-8")
    with pytest.raises(InvalidPromptAsset, match="integrity"):
        FilePromptLoader(tree)


def test_tampered_body_after_recorded_hash_refused(tree):
    path = tree / "demo" / "greeting.v1.0.0.md"
    original = path.read_text(encoding="utf-8")
    body = original.split("---\n", 2)[2]
    path.write_text(original.replace("status: approved", f"status: approved\nsha256: {compute_sha256(body)}")
                    .replace("greeting one", "greeting TAMPERED"), encoding="utf-8")
    with pytest.raises(InvalidPromptAsset, match="integrity"):
        FilePromptLoader(tree)


def test_pointer_recorded_hash_is_verified(tree):
    good = FilePromptLoader(tree).resolve("demo/greeting").sha256
    (tree / "current.json").write_text(
        '{"demo/greeting": {"version": "1.1.0", "sha256": "%s"}}' % good, encoding="utf-8")
    assert FilePromptLoader(tree).resolve("demo/greeting").version == "1.1.0"
    (tree / "current.json").write_text(
        '{"demo/greeting": {"version": "1.1.0", "sha256": "%s"}}' % ("1" * 64), encoding="utf-8")
    with pytest.raises(InvalidPromptAsset, match="integrity"):
        FilePromptLoader(tree).resolve("demo/greeting")


def test_incompatible_consumer(loader):
    asset = loader.get("demo/greeting", "1.0.0")
    asset.check_compatible("fixture-consumer-v1")
    with pytest.raises(IncompatiblePrompt):
        asset.check_compatible("fixture-consumer-v2")
    loader.get("demo/greeting", "1.1.0").check_compatible("fixture-consumer-v2")


def test_path_and_front_matter_must_agree(tree):
    path = tree / "demo" / "greeting.v1.0.0.md"
    path.write_text(path.read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.0.5"),
                    encoding="utf-8")
    with pytest.raises(InvalidPromptAsset, match="path implies"):
        FilePromptLoader(tree)


def test_declared_versions_with_hash_shape(loader):
    declared = loader.declared_versions_with_hash()
    assert set(declared) == {"demo/greeting", "demo/farewell"}
    for family, entry in declared.items():
        asset = loader.resolve(family)
        assert entry == {"version": asset.version, "sha256": asset.sha256}
        assert len(entry["sha256"]) == 64


def test_production_versions_not_wired():
    from src.config_versions import production_versions

    assert set(production_versions()) == {
        "prompt_version", "model_policy_version", "specialist_config_version", "knowledge_version"}


def test_no_network_or_provider_use(tree, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    ld = FilePromptLoader(tree)
    ld.render(ld.resolve("demo/greeting"), {"name": "A", "topic": "B"})
    ld.declared_versions_with_hash()
