"""01C: registry, binding, prompt and authorization catalogue parity, offline."""
import re

import pytest
from pydantic import BaseModel

from src.agent.policies import system_prompt
from src.agent.registry import ToolRegistry, career_tool_registry
from src.agent.tool_authorization import DEFAULT_POLICIES, ToolAuthorizer

EXPECTED = {"AnalyzeJobDescription", "AnalyzeCandidateGaps", "BuildPreparationPlan", "GenerateInterviewQuestions",
            "SearchCareerKnowledge", "ResearchCurrentMarket", "AnalyzeRoleOpportunity", "FindCandidateEvidence",
            "BuildCoachingStrategy", "ProposePreparationMemory", "RequestPracticeHandoff"}


def test_exact_catalogue_matches_binding_and_policy_and_pydantic_contracts():
    registry = career_tool_registry(None)
    registry.assert_policy_parity()
    assert set(registry.names()) == EXPECTED == set(DEFAULT_POLICIES)
    assert {m.__name__ for m in registry.bind_schemas()} == EXPECTED
    catalogue = registry.catalogue()
    for entry, model in zip(catalogue, registry.bind_schemas()):
        assert entry["parameters"] == model.model_json_schema()
        assert entry["description"] == " ".join(model.model_json_schema()["description"].split())
        assert f"- {entry['name']}: {entry['description']}" in system_prompt(registry)
    assert set(re.findall(r"^- (\w+):", system_prompt(registry), re.M)) == EXPECTED


def test_disabled_tool_is_removed_from_both_available_catalogue_and_binding():
    registry = career_tool_registry(None)
    disabled = {"ResearchCurrentMarket"}
    prompt_section = system_prompt(registry, disabled).split("Tools available to you:\n")[1].split("\nRules:")[0]
    assert "ResearchCurrentMarket" not in prompt_section
    assert {m.__name__ for m in registry.bind_schemas(disabled)} == EXPECTED - disabled
    assert {x["name"] for x in registry.catalogue(disabled)} == EXPECTED - disabled


def test_duplicate_and_invalid_registration_never_changes_the_catalogue():
    registry = career_tool_registry(None)
    model = registry.bind_schemas()[0]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(model, lambda a, c: None)
    with pytest.raises(ValueError, match="Pydantic"):
        registry.register(str, lambda a, c: None)
    with pytest.raises(ValueError, match="callable"):
        registry.register(model, None)
    assert set(registry.names()) == EXPECTED


def test_missing_or_extra_policy_is_a_parity_failure_not_a_new_tool():
    registry = career_tool_registry(None, authorizer=ToolAuthorizer(policies={}))
    # The production builder fills every registered tool policy itself.
    registry.assert_policy_parity()
    registry.authorizer._policies.pop("AnalyzeJobDescription")
    with pytest.raises(ValueError, match="policies differ"):
        registry.assert_policy_parity()
    assert set(registry.names()) == EXPECTED


def test_custom_registry_prompt_has_only_its_registered_tool():
    class LocalTool(BaseModel):
        """A bounded local test operation."""
        value: int
    registry = ToolRegistry()
    registry.register(LocalTool, lambda a, c: None)
    prompt = system_prompt(registry)
    assert "- LocalTool: A bounded local test operation." in prompt
    assert "- AnalyzeJobDescription:" not in prompt
