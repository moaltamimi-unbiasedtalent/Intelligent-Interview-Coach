"""Preparation-memory routes — user-scoped, explicit writes only (Phase 7).

Every operation resolves the caller's internal user id and passes it to the memory
application service, which filters by user. One user can never list, fetch or delete
another user's memory (a foreign id returns 404, never another user's data).

Phase 7 memory writes are EXPLICIT and user-initiated (POST). The agent never
persists memory automatically here; agent-proposed, human-approved writes are Phase
8. Identity uses the existing transitional API boundary (see dependencies).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.dependencies import get_current_user_id, get_memory_service
from src.api.schemas.memory import (
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryListResponse,
    MemoryPreviewItem,
    MemoryPreviewResponse,
    MemoryResponse,
    MemoryUpdateRequest,
)
from src.memory import MEMORY_MAX_LOAD_PER_RUN, MemoryCategory

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=MemoryListResponse,
            summary="List the caller's saved preparation memories")
def list_memories(
    category: MemoryCategory | None = Query(default=None),
    service=Depends(get_memory_service),
    user_id: int = Depends(get_current_user_id),
) -> MemoryListResponse:
    items = service.list(
        user_id, category=(category.value if category else None)
    )
    return MemoryListResponse(memories=[MemoryResponse(**m.to_public()) for m in items])


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED,
             summary="Save one preparation memory (explicit, user-initiated)")
def create_memory(
    body: MemoryCreateRequest,
    service=Depends(get_memory_service),
    user_id: int = Depends(get_current_user_id),
) -> MemoryResponse:
    # source_run_id is intentionally NOT accepted from the request body — the
    # server owns provenance/identity/timestamps.
    item = service.create(
        user_id,
        category=body.category.value,
        summary=body.summary,
        target_role=body.target_role,
    )
    return MemoryResponse(**item.to_public())


@router.get("/preview", response_model=MemoryPreviewResponse,
            summary="Preview the memories a new run for a role would load")
def preview_memory(
    target_role: str | None = Query(default=None, max_length=200),
    service=Depends(get_memory_service),
    user_id: int = Depends(get_current_user_id),
) -> MemoryPreviewResponse:
    # Delegates to the SAME load_for_agent selection the agent uses — no drift.
    rows = service.preview_for_agent(user_id, (target_role or "").strip() or None)
    return MemoryPreviewResponse(
        target_role=(target_role or "").strip() or None,
        load_limit=MEMORY_MAX_LOAD_PER_RUN,
        items=[MemoryPreviewItem(**r) for r in rows],
    )


@router.get("/{memory_id}", response_model=MemoryResponse,
            summary="Fetch one of the caller's preparation memories")
def get_memory(
    memory_id: int = Path(..., ge=1),
    service=Depends(get_memory_service),
    user_id: int = Depends(get_current_user_id),
) -> MemoryResponse:
    item = service.get(user_id, memory_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return MemoryResponse(**item.to_public())


@router.patch("/{memory_id}", response_model=MemoryResponse,
              summary="Edit / pin one of the caller's preparation memories")
def update_memory(
    body: MemoryUpdateRequest,
    memory_id: int = Path(..., ge=1),
    service=Depends(get_memory_service),
    user_id: int = Depends(get_current_user_id),
) -> MemoryResponse:
    provided = body.model_fields_set
    # Only fields the client explicitly sent are applied — an omitted field is left
    # untouched, while ``target_role: null`` explicitly clears the role. Extra keys
    # (user_id/source_run_id/…) are already rejected by the schema (extra=forbid).
    kwargs: dict = {}
    if "category" in provided and body.category is not None:
        kwargs["category"] = body.category.value
    if "summary" in provided and body.summary is not None:
        kwargs["summary"] = body.summary
    if "target_role" in provided:
        kwargs["target_role"] = body.target_role  # may be None → clears the role
    if "pinned" in provided and body.pinned is not None:
        kwargs["pinned"] = body.pinned
    if not kwargs:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    item = service.update(user_id, memory_id, **kwargs)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return MemoryResponse(**item.to_public())


@router.delete("/{memory_id}", response_model=MemoryDeleteResponse,
               summary="Delete one of the caller's preparation memories")
def delete_memory(
    memory_id: int = Path(..., ge=1),
    service=Depends(get_memory_service),
    user_id: int = Depends(get_current_user_id),
) -> MemoryDeleteResponse:
    deleted = service.delete(user_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return MemoryDeleteResponse(deleted=True, id=memory_id)
