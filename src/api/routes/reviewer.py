"""Reviewer / admin diagnostics routes (Capstone P6, §12/§30/§41).

A bounded, PLATFORM_ADMIN-gated technical surface — NOT a full admin console and NOT for
normal candidates. It exposes safe, read-only knowledge governance, retention inventory,
production config versions and Prompt Lab experiment metadata. It returns NO embeddings,
secrets, system prompts, candidate-private content or chain-of-thought, and it never
mutates production configuration.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import require_platform_admin

router = APIRouter(prefix="/reviewer", tags=["reviewer"], dependencies=[Depends(require_platform_admin)])


@router.get("/knowledge/readiness", summary="Deterministic knowledge readiness (admin)")
def knowledge_readiness() -> dict:
    from src.copilot.knowledge import governance as gov
    return gov.overall_readiness()


@router.get("/knowledge/manifest", summary="Knowledge manifest (admin)")
def knowledge_manifest() -> dict:
    from src.copilot.knowledge import governance as gov
    return gov.knowledge_manifest()


@router.get("/knowledge/source-health", summary="Per-source health (admin)")
def source_health() -> dict:
    from src.copilot.knowledge import governance as gov
    return {"sources": gov.source_health()}


@router.get("/knowledge/coverage", summary="Knowledge coverage matrix (admin)")
def coverage() -> dict:
    from src.copilot.knowledge import governance as gov
    return gov.coverage_matrix()


@router.get("/knowledge/language-boundary", summary="7-language knowledge boundary (admin)")
def language_boundary() -> dict:
    from src.copilot.knowledge import governance as gov
    return {"languages": gov.language_boundary()}


@router.get("/config-versions", summary="Production configuration versions (admin)")
def config_versions() -> dict:
    from src.config_versions import production_versions
    return production_versions()


@router.get("/retention/inventory", summary="Retention inventory (admin)")
def retention_inventory() -> dict:
    from src.application.retention_service import retention_inventory as inv
    return {"inventory": inv()}


@router.get("/prompt-lab/experiments", summary="Prompt Lab experiments (admin)")
def list_experiments() -> dict:
    from src.application.prompt_lab import PromptLabService
    return {"experiments": PromptLabService().list()}


@router.get("/prompt-lab/experiments/{experiment_id}", summary="One Prompt Lab experiment (admin)")
def get_experiment(experiment_id: str) -> dict:
    from src.application.prompt_lab import PromptLabService
    exp = PromptLabService().get(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return exp.model_dump(mode="json")
