"""Candidate-facing support schemas (P10B-W10.3). Allowlist, ``extra="forbid"``.

These are the ONLY shapes a candidate ever receives. They deliberately have no internal-note, priority,
assignee, operator-identity or audit field, so a leak is structurally impossible rather than a matter of
careful filtering (guarded by tests and ``scripts/eval_admin_support.py``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TicketCreateRequest(_Strict):
    category: str = Field(max_length=32)
    subject: str = Field(max_length=400)   # hard cap; the service enforces the 200-character rule
    message: str = Field(max_length=20000)  # hard cap; the service enforces the 5000-character rule
    request_id: str | None = Field(default=None, max_length=128)
    source_route: str | None = Field(default=None, max_length=400)


class TicketReplyRequest(_Strict):
    message: str = Field(max_length=20000)
    request_id: str | None = Field(default=None, max_length=128)


class TicketSummary(_Strict):
    public_id: str
    category: str
    status: str
    subject: str
    created_at: str | None
    updated_at: str | None


class TicketList(_Strict):
    items: list[TicketSummary]
    total: int
    page: int
    page_size: int


class ThreadMessage(_Strict):
    id: int
    author_kind: str            # "candidate" or "support"; no operator identity is exposed
    body: str
    created_at: str | None


class TicketDetail(TicketSummary):
    can_reply: bool
    messages: list[ThreadMessage]
