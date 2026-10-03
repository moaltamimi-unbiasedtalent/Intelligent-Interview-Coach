"""W10.9 job types for governed knowledge (P10B-W10.8). Code-defined; payload is a version public id only (never text)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.jobs.registry import JobContext, JobTypeDef
from src.knowledge_admin import policy as P, runtime as R


class VersionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


def _summary(p: VersionPayload) -> dict:
    return {"version": p.version_id}


def _parse(p: VersionPayload, ctx: JobContext) -> None:
    R.run_parse(p.version_id, ctx)


def _index(p: VersionPayload, ctx: JobContext) -> None:
    R.run_index(p.version_id, ctx)


def _remove(p: VersionPayload, ctx: JobContext) -> None:
    R.run_remove(p.version_id, ctx)


def job_types() -> list[JobTypeDef]:
    common = dict(payload_model=VersionPayload, summarize=_summary, admin_enqueue=False, manual_retry=True,
                  dependencies=("knowledge", "vector_store"))
    return [
        JobTypeDef(code=P.JOB_PARSE, label="Knowledge: scan and parse", handler=_parse, max_attempts=3, lease_seconds=120,
                   backoff_base_seconds=30, backoff_cap_seconds=300,
                   idempotency="Guarded state check; preview/size are overwritten with checksum-anchored identical values.", **common),
        JobTypeDef(code=P.JOB_INDEX, label="Knowledge: index approved version", handler=_index, max_attempts=3, lease_seconds=300,
                   backoff_base_seconds=60, backoff_cap_seconds=600,
                   idempotency="Deterministic chunk ids (version id + chunk text) skipped when present; index record is an upsert.", **common),
        JobTypeDef(code=P.JOB_REMOVE, label="Knowledge: remove retired version from the index", handler=_remove, max_attempts=5,
                   lease_seconds=120, backoff_base_seconds=60, backoff_cap_seconds=900,
                   idempotency="Delete-by-version is idempotent; retrieval never depends on it succeeding.", **common),
    ]
