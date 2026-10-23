"""01B: production prompt assets, fail-closed loading, rollback, attribution and packaging. Offline."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from src import prompt_assets
from src.agent import policies
from src.application.agent_service import AgentApplicationService
from src.agent.eval import _scripted_model, build_eval_career, evaluate, load_cases
from src.agent.models import AgentRunRequest
from src.application.prompt_lab import EvaluationSet, PromptLabService, Variant
from src.config_versions import production_versions, prompt_version
from src.prompt_loader import (
    FilePromptLoader, IncompatiblePrompt, InvalidPromptAsset, MissingPromptVersion, VariableMismatch,
)

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
EXPECTED_FAMILY_COUNT = 45  # 06C: + rag/response_language (the Career-chat language directive moved from an inline literal into a versioned asset)


@pytest.fixture
def prompt_tree(tmp_path):
    """A writable copy of prompts/ the test can edit; the cached loader is restored afterwards."""
    dest = tmp_path / "prompts"
    shutil.copytree(PROMPTS, dest)
    yield dest
    prompt_assets.reload_for_tests()


def _write_version(root: Path, family: str, version: str, body: str, variables: str = "[]",
                   status: str = "approved", compat: str | None = None, sha: bool = True) -> Path:
    d, name = family.split("/")
    base = next((root / d).glob(f"{name}.v*.md"))
    compat = compat or base.read_text(encoding="utf-8").split("compatible_with: ")[1].split("\n")[0]
    fm = (f"---\nid: {family.replace('/', '.')}\nfamily: {family}\nversion: {version}\nvariables: {variables}\n"
          f"compatible_with: {compat}\ndescription: test\nstatus: {status}\n"
          + (f"sha256: {hashlib.sha256(body.encode()).hexdigest()}\n" if sha else "") + "---\n")
    path = root / d / f"{name}.v{version}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


def _pointer(root: Path, family: str, version: str, sha: str | None = None) -> None:
    ptr = json.loads((root / "current.json").read_text(encoding="utf-8"))
    ptr[family] = {"version": version, "sha256": sha} if sha else version
    (root / "current.json").write_text(json.dumps(ptr), encoding="utf-8")


# ---------------------------------------------------------------- inventory and integrity ----------------
def test_production_tree_is_complete_valid_and_pinned():
    loader = FilePromptLoader(PROMPTS)
    assert len(loader.families()) == EXPECTED_FAMILY_COUNT
    pointer = json.loads((PROMPTS / "current.json").read_text(encoding="utf-8"))
    assert sorted(pointer) == loader.families()
    for family in loader.families():
        asset = loader.resolve(family)
        assert asset.version == ("1.1.0" if family == "agent/system" else "1.0.0") and asset.status == "approved"
        assert asset.recorded_sha256 == asset.sha256 == pointer[family]["sha256"]
        assert asset.compatible_with, family
    assert loader.declared_versions_with_hash() == prompt_assets.effective_versions()


def test_every_consumer_contract_id_is_used_and_declared():
    declared = {c for f in FilePromptLoader(PROMPTS).families()
                for c in FilePromptLoader(PROMPTS).resolve(f).compatible_with}
    assert declared == {"agent.policies", "agent.judge", "interview.prompts", "coaching.style", "rag.prompts",
                        "rag.synthesis", "rag.translation", "career.tools"}


def test_assets_contain_no_secret_shaped_text():
    for path in PROMPTS.rglob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert not re.search(r"\bsk-[a-z0-9]", text), path.name
        for bad in ("api_key", "bearer ", "openrouter_api"):
            assert bad not in text, f"{path.name} contains {bad}"


# ---------------------------------------------------------------- errors ----------------------------------
def test_missing_family_and_missing_version_are_refused():
    with pytest.raises(MissingPromptVersion):
        prompt_assets.asset("agent/nope", "agent.policies")
    loader = prompt_assets.get_loader()
    with pytest.raises(MissingPromptVersion):
        loader.get("agent/system", "9.9.9")


def test_incompatible_consumer_is_refused():
    with pytest.raises(IncompatiblePrompt):
        prompt_assets.render("agent/response_language", "interview.prompts", language_name="German")


def test_variable_mismatch_is_refused():
    with pytest.raises(VariableMismatch):
        prompt_assets.render("agent/response_language", "agent.policies")
    with pytest.raises(VariableMismatch):
        prompt_assets.render("agent/response_language", "agent.policies", language_name="x", extra="y")


def test_undeclared_placeholder_in_an_asset_fails_the_load(prompt_tree):
    _write_version(prompt_tree, "agent/system", "1.0.1", "Hello {undeclared}")
    with pytest.raises(InvalidPromptAsset):
        FilePromptLoader(prompt_tree)


def test_missing_assets_fail_closed_with_a_clear_error(tmp_path):
    prompt_assets.reload_for_tests(tmp_path / "does-not-exist")
    try:
        with pytest.raises(MissingPromptVersion, match="not found"):
            prompt_assets.get_loader()
        with pytest.raises(MissingPromptVersion):
            prompt_assets.render("agent/system", "agent.policies")
    finally:
        prompt_assets.reload_for_tests()


def test_tampered_asset_fails_integrity(prompt_tree):
    path = next((prompt_tree / "agent").glob("system.v1.0.0.md"))
    path.write_text(path.read_text(encoding="utf-8") + " tampered", encoding="utf-8")
    with pytest.raises(InvalidPromptAsset, match="integrity"):
        FilePromptLoader(prompt_tree)


def test_pointer_hash_mismatch_is_refused(prompt_tree):
    _pointer(prompt_tree, "agent/system", "1.0.0", sha="0" * 64)
    with pytest.raises(InvalidPromptAsset, match="pointer integrity"):
        FilePromptLoader(prompt_tree).resolve("agent/system")


def test_draft_never_resolves_even_when_pointed_at(prompt_tree):
    _write_version(prompt_tree, "agent/system", "1.1.0", "draft text", status="draft")
    _pointer(prompt_tree, "agent/system", "1.1.0")
    with pytest.raises(MissingPromptVersion, match="draft"):
        FilePromptLoader(prompt_tree).resolve("agent/system")


# ---------------------------------------------------------------- rollback with no code change --------------
def test_pointer_change_rolls_back_and_forward_with_attribution_and_no_code_change(prompt_tree):
    base = prompt_assets.effective_versions(["agent/response_language"])["agent/response_language"]
    original = prompt_assets.render("agent/response_language", "agent.policies", language_name="German")
    new_body = "REVISED DIRECTIVE for {language_name}."
    _write_version(prompt_tree, "agent/response_language", "1.1.0", new_body, variables="[language_name]")
    _pointer(prompt_tree, "agent/response_language", "1.1.0")

    prompt_assets.reload_for_tests(prompt_tree)  # a new process reading the edited tree
    forward = prompt_assets.effective_versions(["agent/response_language"])["agent/response_language"]
    assert forward["version"] == "1.1.0" and forward["sha256"] != base["sha256"]
    assert policies.response_language_directive("de") == "REVISED DIRECTIVE for German."
    assert policies.run_prompt_versions("de", [])["agent/response_language"] == forward

    _pointer(prompt_tree, "agent/response_language", "1.0.0")  # rollback: a pointer edit only
    prompt_assets.reload_for_tests(prompt_tree)
    back = prompt_assets.effective_versions(["agent/response_language"])["agent/response_language"]
    assert back == base
    assert policies.response_language_directive("de") == original
    assert policies.run_prompt_versions("de", [])["agent/response_language"] == base


def test_prompt_set_version_changes_when_an_effective_version_changes(prompt_tree):
    before = prompt_assets.prompt_set_version()
    _write_version(prompt_tree, "interview/mission", "1.0.1", "Different mission.")
    _pointer(prompt_tree, "interview/mission", "1.0.1")
    prompt_assets.reload_for_tests(prompt_tree)
    after = prompt_assets.prompt_set_version()
    assert before != after and after.startswith("promptset-")
    _pointer(prompt_tree, "interview/mission", "1.0.0")
    prompt_assets.reload_for_tests(prompt_tree)
    assert prompt_assets.prompt_set_version() == before


def test_without_a_pointer_the_highest_approved_version_is_current(prompt_tree):
    _write_version(prompt_tree, "agent/judge", "1.2.0", "Judge v1.2.")
    _write_version(prompt_tree, "agent/judge", "1.10.0", "Judge v1.10.")
    _write_version(prompt_tree, "agent/judge", "2.0.0", "Judge draft", status="draft")
    (prompt_tree / "current.json").write_text("{}", encoding="utf-8")
    assert FilePromptLoader(prompt_tree).resolve("agent/judge").version == "1.10.0"


# ---------------------------------------------------------------- production_versions parity ----------------
def test_production_versions_keeps_legacy_keys_and_adds_version_plus_hash():
    versions = production_versions()
    assert {"prompt_version", "model_policy_version", "specialist_config_version", "knowledge_version"} <= set(versions)
    # prompt_version keeps its exact historical meaning: a hash of Mo's system prompt (unchanged by 01B).
    assert versions["prompt_version"] == prompt_version() == "prompt-" + hashlib.sha256(policies.SYSTEM_PROMPT.encode()).hexdigest()[:12]
    assets = versions["prompt_assets"]
    assert sorted(assets) == FilePromptLoader(PROMPTS).families()
    assert versions["prompt_set_version"] == prompt_assets.prompt_set_version()
    for family, entry in assets.items():
        d, name = family.split("/")
        body = (PROMPTS / d / f"{name}.v{entry['version']}.md").read_text(encoding="utf-8").split("\n---\n", 1)[1]
        assert entry["sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
    json.dumps(versions)  # JSON-safe (reviewer route)


def test_production_versions_exposes_hashes_never_prompt_text():
    blob = json.dumps(production_versions())
    assert "IDENTITY" not in blob and "You are Mo" not in blob and "OPERATING RULES" not in blob


# ---------------------------------------------------------------- run attribution ----------------------------
def _run(goal="Hello", script=(), **request):
    svc = AgentApplicationService(model_factory=lambda: _scripted_model(list(script)),
                                  career_service=build_eval_career())
    return svc.run(AgentRunRequest(goal=goal, user_id="eval", **request))


def test_agent_run_result_records_effective_prompt_versions_without_text():
    default = _run()
    assert set(default.prompt_versions) == {"agent/system"}
    assert default.prompt_versions == prompt_assets.effective_versions(["agent/system"])
    german = _run(conversation_language="de", coaching_style="direct")
    assert set(german.prompt_versions) == {"agent/system", "agent/response_language", "coaching/wrapper",
                                           "coaching/directives"}
    english = _run(conversation_language="en", coaching_style="balanced")
    assert set(english.prompt_versions) == {"agent/system"}   # no directive added, none recorded
    blob = json.dumps(german.prompt_versions)
    assert "IDENTITY" not in blob and "RESPONSE LANGUAGE" not in blob
    assert all(set(v) == {"version", "sha256"} for v in german.prompt_versions.values())


def test_agent_run_records_prompts_of_the_model_backed_tools_it_executed():
    jd = "Senior nurse role. Requires triage skills."
    result = _run(goal="Prepare me", script=[
        {"name": "AnalyzeJobDescription", "args": {"job_description": jd}},
        {"name": "GenerateInterviewQuestions", "args": {"role": "Nurse"}}])
    assert {"AnalyzeJobDescription", "GenerateInterviewQuestions"} <= set(result.tools_used)
    assert {"career/job_analysis", "career/question_generation"} <= set(result.prompt_versions)


def test_evaluation_results_carry_the_effective_prompt_versions():
    metrics = evaluate(load_cases()[:6], build_eval_career())
    assert "agent/system" in metrics["prompt_versions"]
    assert all("prompt_versions" in r for r in metrics["results"])


# ---------------------------------------------------------------- Prompt Lab attribution --------------------
def test_prompt_lab_runs_are_attributable_to_prompt_version_model_and_configuration(tmp_path):
    svc = PromptLabService(base_dir=tmp_path)
    es = EvaluationSet(evaluation_set_id="mp", version="1.0", evaluator="model_policy_floors",
                       cases=[{"user_profile": "fast"}])
    exp = svc.create_experiment(
        title="t", hypothesis="h", created_by="admin", evaluation_set=es,
        variants=[Variant(variant_id="base", label="b", is_baseline=True, config={"operation": "orchestration"}),
                  Variant(variant_id="v2", label="v", config={"operation": "final_response"}),
                  Variant(variant_id="v3", label="w", config={"operation": "orchestration"})])
    done = svc.run_experiment(exp.experiment_id)
    base, v2, v3 = done.runs
    for run in done.runs:
        assert run.prompt_assets == prompt_assets.effective_versions()
        assert run.production_versions["prompt_set_version"] == prompt_assets.prompt_set_version()
        assert run.production_versions["model_policy_version"]
        assert set(run.model_profiles) == {"fast", "balanced", "advanced"} and all(run.model_profiles.values())
        assert all(isinstance(v, str) for v in run.production_versions.values())
    assert base.configuration_sha256 == v3.configuration_sha256 != v2.configuration_sha256
    reloaded = PromptLabService(base_dir=tmp_path).get(exp.experiment_id)
    assert reloaded.runs[0].prompt_assets == base.prompt_assets


def test_prompt_lab_experiments_stored_before_01b_still_load(tmp_path):
    svc = PromptLabService(base_dir=tmp_path)
    es = EvaluationSet(evaluation_set_id="mp", version="1.0", evaluator="model_policy_floors", cases=[{}])
    exp = svc.run_experiment(svc.create_experiment(
        title="t", hypothesis="h", created_by="a", evaluation_set=es,
        variants=[Variant(variant_id="a", label="a", is_baseline=True)]).experiment_id)
    path = next(tmp_path.rglob(f"*{exp.experiment_id}*"))
    data = json.loads(path.read_text(encoding="utf-8"))
    for run in data["runs"]:
        for key in ("prompt_assets", "model_profiles", "configuration_sha256"):
            run.pop(key)
    path.write_text(json.dumps(data), encoding="utf-8")
    old = PromptLabService(base_dir=tmp_path).get(exp.experiment_id)
    assert old.runs[0].prompt_assets == {} and old.runs[0].configuration_sha256 == ""


# ---------------------------------------------------------------- packaging ---------------------------------
def test_prompt_root_is_next_to_src_and_shipped_in_the_api_image():
    assert prompt_assets.PROMPT_ROOT == ROOT / "prompts" and (ROOT / "src").is_dir()
    dockerfile = (ROOT / "deploy" / "Dockerfile.api").read_text(encoding="utf-8")
    assert "COPY prompts ./prompts" in dockerfile
    assert "COPY src ./src" in dockerfile            # same /app parent, so PROMPT_ROOT == /app/prompts
    ignored = [ln.strip().rstrip("/") for ln in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
    assert "prompts" not in ignored and "prompts/**" not in ignored


def test_no_production_module_keeps_a_literal_prompt_fallback():
    """The migrated modules must not carry a second copy of the text (single source of truth)."""
    for rel, needle in (
        ("src/agent/policies.py", "You are Mo, the AI Coach"),
        ("src/prompts.py", "OPERATING RULES"),
        ("src/copilot/rag/prompts.py", "Grounding rules"),
        ("src/copilot/rag/synthesis.py", "You are the Career Intelligence Copilot"),
        ("src/copilot/rag/translation.py", "You are the query-understanding"),
        ("src/agent/judge.py", "strict, fair evaluator"),
        ("src/coaching_style.py", "stretching coaching tone"),
    ):
        assert needle not in (ROOT / rel).read_text(encoding="utf-8"), rel
