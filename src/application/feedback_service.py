"""Candidate feedback application service (Streamlit/FastAPI-free) — post-Sprint 4 P5.

Validates a rating, VERIFIES the rated target belongs to the current user, upserts one
current rating per logical output, and aggregates safe metrics. Ownership is proven via
injected per-surface verifiers (the agent run / interview session must belong to the
caller); a foreign or unknown target behaves like not-found and never discloses whether
it exists for someone else.

Feedback is NOT a learning signal that changes the app automatically — the comment is
UNTRUSTED user data, stored and displayed as bounded text only, never fed into any
prompt, memory, tool or policy (§25). Improvement is a human-reviewed engineering loop.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from src.application.errors import ValidationError
from src.feedback import (
    FEEDBACK_MAX_COMMENT_CHARS,
    FeedbackItem,
    FeedbackRating,
    FeedbackSurface,
    normalize_comment,
)
from src.repository import FeedbackRepository

__all__ = ["FeedbackApplicationService", "TargetVerifier"]

# Proves an EXACT feedback target. Returns True ONLY if this precise rated output
# exists AND belongs to this user — e.g. an Agent response with that response_id, an
# Interview question that has a completed evaluation, or a session that has generated
# its final report. Owning the parent run/session is necessary but NOT sufficient.
# Fails closed: any parse/service/missing-resource error must return False.
TargetVerifier = Callable[[str, int], bool]


class FeedbackApplicationService:
    """User-scoped feedback operations for any frontend."""

    def __init__(
        self,
        repository: FeedbackRepository,
        *,
        target_verifiers: dict[str, TargetVerifier] | None = None,
        observability: Any | None = None,
    ) -> None:
        self._repo = repository
        self._verifiers = dict(target_verifiers or {})
        self._obs = observability  # optional ObservabilitySink (NoOp by default)

    def _verify_target(self, surface: FeedbackSurface, target_id: str, user_id: int) -> bool:
        verifier = self._verifiers.get(surface.value)
        if verifier is None:
            return False  # cannot prove ownership → treat as not-found (fail closed)
        try:
            return bool(verifier(target_id, user_id))
        except Exception:  # noqa: BLE001 - a verifier failure is never an ownership grant
            return False

    def submit(
        self, user_id: int, *, surface: str, target_id: str, rating: str,
        comment: str | None = None,
    ) -> FeedbackItem | None:
        """Validate + verify ownership + upsert. Returns None when the target is not
        owned by the user (a not-found), so a caller maps it to 404 without disclosure.
        A rating change updates the SAME record (never a duplicate)."""
        surf = self._parse_surface(surface)
        try:
            rat = FeedbackRating.from_value(rating)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        tid = (target_id or "").strip()
        if not tid:
            raise ValidationError("A feedback target is required.")
        cleaned = normalize_comment(comment)
        if cleaned and len(cleaned) > FEEDBACK_MAX_COMMENT_CHARS:
            raise ValidationError(
                f"A comment must be {FEEDBACK_MAX_COMMENT_CHARS} characters or fewer.")

        if not self._verify_target(surf, tid, user_id):
            return None

        item = self._repo.upsert(
            user_id, surface=surf.value, target_id=tid, rating=rat.value, comment=cleaned)
        # Safe observability: surface + rating only (never the comment or rated content).
        if self._obs is not None:
            try:
                self._obs.feedback_event(surface=surf.value, rating=rat.value)
            except Exception:  # noqa: BLE001 - telemetry is non-critical, never fails feedback
                pass
        return item

    def get(self, user_id: int, surface: str, target_id: str) -> FeedbackItem | None:
        surf = self._parse_surface(surface)
        return self._repo.get(user_id, surf.value, (target_id or "").strip())

    def delete(self, user_id: int, surface: str, target_id: str) -> bool:
        surf = self._parse_surface(surface)
        return self._repo.delete(user_id, surf.value, (target_id or "").strip())

    def metrics(self, *, days: int | None = None) -> dict:
        """Aggregate metrics across all users (no raw comments, no identities)."""
        since = None
        if days:
            from src.persistence import utcnow

            since = utcnow() - timedelta(days=days)
        return self._repo.metrics(since=since)

    @staticmethod
    def _parse_surface(surface: str) -> FeedbackSurface:
        try:
            return FeedbackSurface.from_value(surface)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
