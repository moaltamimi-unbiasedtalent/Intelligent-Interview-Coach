"""Allowlist schemas of the 03C bulk Admin Users actions (``extra="forbid"``). Counts and reason codes only: no email, no account id list in a response, no
token, no candidate content."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BulkPreview(_Strict):
    action: Literal["force-signout", "expire-verification"]
    requested: int
    unique: int
    eligible: int
    excluded: int
    excluded_by_reason: dict[str, int]
    max_batch: int
    preview_revision: str


class BulkExecuteBody(_Strict):
    account_ids: list[int] = Field(min_length=1, max_length=100)
    preview_revision: str = Field(min_length=8, max_length=32, pattern=r"^[0-9a-f]+$")
    reason: str = Field(min_length=3, max_length=200)


class BulkResult(_Strict):
    action: Literal["force-signout", "expire-verification"]
    batch_id: str
    status: Literal["complete", "partial", "none_applied"]
    requested: int
    unique: int
    applied: int
    skipped: int
    skipped_by_reason: dict[str, int]
    failed: int
    failed_by_reason: dict[str, int]
    replayed: bool
