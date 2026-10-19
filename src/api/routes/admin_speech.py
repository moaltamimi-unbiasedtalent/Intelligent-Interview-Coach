"""Admin governance of the server-side speech providers (W12.4E). Every route declares an explicit permission.

* GET reads need ``platform.flags.read``; a change needs ``platform.config.manage`` (the existing owner of operator configuration; no new permission). A change carries the expected revision and a reason and is
  audited in the same transaction.
* Configuration is SELECTION and POLICY only. There is no route that takes a path, a command, an endpoint, a model-loading instruction or a secret, and no route that contacts a provider.
* The overview reports provider readiness as separate states and states plainly that configured is not operational.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_request_id, get_speech_governance_service, get_speech_runtime, require_permission
from src.api.schemas.speech import SpeechConfigChange, SpeechConfigView, SpeechOverview
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.speech import policy
from src.speech.governance import (
    SpeechGovernanceConflict, SpeechGovernanceUnavailable, SpeechGovernanceUnsupportedEnvironment, SpeechGovernanceValidationError,
)

router = APIRouter(prefix="/admin/speech", tags=["admin-speech"])

NOTE = ("Server-side speech is governed here but is NOT active: enabling a provider records a decision only. A provider executes only when the code authorization constants allow it, the dependency and model "
        "are present (never downloaded automatically) and genuine model validation exists. Candidate audio is never stored. The browser speech paths are governed separately by the two fallback settings.")


def _facts() -> dict:
    return {"openai_whisper": {"languages": list(policy.WHISPER_CAPABILITY.languages), **policy.WHISPER_CAPABILITY.notes},
            "kyutai_pocket_tts": {"languages": list(policy.KYUTAI_CAPABILITY.languages), "unverified_languages": list(policy.KYUTAI_CAPABILITY.unverified_languages), **policy.KYUTAI_CAPABILITY.notes}}


@router.get("", response_model=SpeechOverview, summary="Speech governance, provider readiness and the language matrix (no provider is contacted)")
def speech_overview(_p=Depends(require_permission(perm.FLAGS_READ)), svc=Depends(get_speech_governance_service), runtime=Depends(get_speech_runtime)) -> SpeechOverview:
    try:
        cfg = svc.get()
    except SpeechGovernanceUnavailable:
        raise HTTPException(status_code=503, detail="Speech settings are unavailable right now.")
    readiness = runtime.readiness()
    return SpeechOverview(environment=svc.environment or "unsupported", config=SpeechConfigView(**cfg.public()), stt=readiness["stt"], tts=readiness["tts"], language_matrix=runtime.capability_matrix(),
                          provider_facts=_facts(), authorization={"server_speech_providers": policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED, "hosted_whisper_api_transport": policy.WHISPER_API_TRANSPORT_AUTHORIZED,
                                                                   "model_downloads": policy.MODEL_DOWNLOADS_AUTHORIZED, "voice_cloning": policy.VOICE_CLONING_ENABLED}, note=NOTE)


@router.put("", response_model=SpeechConfigView, summary="Change speech governance (expected revision, required reason, same-transaction audit)")
def change_speech_config(body: SpeechConfigChange, request: Request, principal=Depends(require_permission(perm.CONFIG_MANAGE)), svc=Depends(get_speech_governance_service)) -> SpeechConfigView:
    patch = {k: v for k, v in body.model_dump(exclude={"expected_revision", "reason"}).items() if v is not None}

    def audit_for(info: dict) -> dict:
        return A.build_audit(event_type=A.ADMIN_SPEECH_CONFIG_CHANGED, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="speech_governance", reason=body.reason[:200])

    try:
        cfg = svc.update(patch, expected_revision=body.expected_revision, reason=body.reason, actor_user_id=principal.user_id, audit_for=audit_for)
    except SpeechGovernanceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (SpeechGovernanceConflict, SpeechGovernanceUnsupportedEnvironment) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SpeechGovernanceUnavailable:
        raise HTTPException(status_code=503, detail="Speech settings are unavailable right now.")
    return SpeechConfigView(**cfg.public())
