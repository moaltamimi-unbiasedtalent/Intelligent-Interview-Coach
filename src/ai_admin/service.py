"""AIConfigService (P10B-W10.7): the governed lifecycle DRAFT -> VALIDATE -> EVALUATE -> APPROVE -> ACTIVATE -> ROLLBACK / RETIRE.

THE INVARIANT: an AI configuration cannot become active without a PASSED evaluation of its exact hash and a DISTINCT second approver.
There is no force flag and no bypass route: ``activate`` re-derives every precondition from stored facts at activation time (it trusts no
status field alone), the DB forbids a requester deciding their own approval, and the resolver independently re-verifies the hash of whatever
it loads. The service never calls a provider and never reads a secret.

* Content is frozen (hash-pinned) when a draft is validated; only drafts are editable. A change is a NEW version.
* An approval, an evaluation and an activation each name one config hash; a mismatch at any step fails closed.
* Production activation requires that the same version was previously activated in staging.
* Every mutation writes its audit row in the SAME transaction (an audit failure rolls the change back).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from src.admin_repository import _page, _stage
from src.ai_admin import catalogue as C
from src.ai_admin import config as K
from src.ai_admin.evaluator import EVALUATOR_VERSION, evaluate
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import (
    ACCOUNT_STATUS_ACTIVE, AIConfigActivation as ACT, AIConfigApproval as APR, AIConfigEvaluation as EV, AIConfigVersion as V, User, utcnow,
)

JOB_EVALUATE = "ai_evaluate_config"
ENVIRONMENTS = ("development", "staging", "production")
MAX_NAME, MAX_NOTES, MAX_REASON = 80, 300, 300
EDITABLE = ("draft",)


class AINotFound(Exception):
    pass


class AIValidationError(Exception):
    pass


class AIConflict(Exception):
    pass


class AIForbidden(Exception):
    pass


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _text(value: Any, field: str, limit: int, *, required: bool) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if (required and not text) or len(text) > limit or "\x00" in text:
        raise AIValidationError(f"{field} is required (up to {limit} characters)." if required else f"{field} must be at most {limit} characters.")
    return text


class AIConfigService:
    def __init__(self, session_factory, *, jobs: Any = None, resolver: Any = None, environment: str | None = "from_process",
                 clock: Callable[[], datetime] = utcnow) -> None:
        # The activation environment is decided by the SERVER (API_ENV), never by a caller. Tests and fixtures may inject it. None = unsupported.
        if environment == "from_process":
            from src.ai_admin.resolver import environment_name
            environment = environment_name()
        self.environment = environment
        self._sf = session_factory
        self._jobs = jobs
        self._resolver = resolver
        self._clock = clock

    # ------------------------------------------------------------------ views
    @staticmethod
    def catalogue_view() -> dict:
        items = [{"id": e.id, "display_name": e.display_name, "tier": e.tier.value, "allowed_profiles": [p.value for p in e.allowed_profiles],
                  "provider_slug": e.slug, "supports_tools": e.supports_tools, "supports_structured_output": e.supports_structured_output,
                  "supports_temperature": e.supports_temperature, "cost_class": e.cost_class, "note": e.note} for e in C.CATALOGUE.values()]
        return {"version": C.CATALOGUE_VERSION, "items": items,
                "note": "The approved catalogue is defined in code. A configuration selects an entry by id; it can never supply a provider model name."}

    @staticmethod
    def code_defined_view() -> dict:
        """What a configuration may NOT change, listed for the Admin UI (read-only)."""
        from src.llm.policy import OPERATION_POLICY, ModelCapability

        ops = []
        for op, p in OPERATION_POLICY.items():
            tunable = op in K.TUNABLE_OPERATIONS
            ops.append({"operation": op.value, "capability": p.capability.value, "min_capability": p.min_capability.value,
                        "fallback_floor": p.fallback_floor.value, "structured_output": p.structured_output, "requires_tools": p.requires_tools,
                        "tunable": tunable, "no_runtime_path": not tunable and p.capability not in (ModelCapability.NONE, ModelCapability.REALTIME), "deterministic": p.capability is ModelCapability.NONE,
                        "realtime": p.capability is ModelCapability.REALTIME,
                        "code_values": {"max_output_tokens": p.max_output_tokens, "timeout_s": p.timeout_s, "max_retries": p.max_retries}})
        return {"operations": ops,
                "tunable_fields": {k: {"min": lo, "max": hi} for k, (lo, hi, _i) in K.TUNABLES.items()},
                "note": "Capability, minimum tier, fallback floor, structured-output and tool flags, deterministic and realtime operations, the three "
                        "specialists, the Interview session profile, prompts and secrets are code-defined and not configurable here."}

    def _version_view(self, v: V, s, *, detail: bool = False) -> dict:
        def email(uid):
            u = s.get(User, uid) if uid else None
            return u.email if u else None
        active_in = [a.environment for a in s.scalars(select(ACT).where(ACT.config_version_id == v.id, ACT.deactivated_at.is_(None))).all()]
        out = {"public_id": v.public_id, "version": v.version, "name": v.name, "notes": v.notes, "state": v.state, "content_hash": v.config_hash,
               "catalogue_version": v.catalogue_version, "created_by_email": email(v.created_by_user_id), "created_by_user_id": v.created_by_user_id,
               "created_at": _iso(v.created_at), "validated_at": _iso(v.validated_at), "retired_at": _iso(v.retired_at), "active_in": sorted(active_in)}
        if detail:
            latest = s.scalar(select(EV).where(EV.config_version_id == v.id).order_by(EV.id.desc()))
            out.update({
                "settings": dict(v.config_json or {}), "validation": list((v.validation_json or {}).get("checks", [])),
                "validation_passed": bool((v.validation_json or {}).get("passed")),
                "changed_from_baseline": K.diff_from_baseline(K.normalise(v.config_json)),
                "evaluations": [self._eval_view(e) for e in s.scalars(select(EV).where(EV.config_version_id == v.id).order_by(EV.id.desc()).limit(10)).all()],
                "approvals": [self._approval_view(a, s) for a in s.scalars(select(APR).where(APR.config_version_id == v.id).order_by(APR.id.desc())).all()],
                "activations": [self._activation_view(a, s) for a in s.scalars(select(ACT).where(ACT.config_version_id == v.id).order_by(ACT.id.desc()).limit(20)).all()],
                "latest_evaluation_passed": bool(latest and latest.status == "passed" and latest.config_hash == v.config_hash)})
        return out

    @staticmethod
    def _eval_view(e: EV) -> dict:
        return {"public_id": e.public_id, "content_hash": e.config_hash, "evaluator_version": e.evaluator_version, "status": e.status,
                "checks": list(e.checks_json or []), "summary": dict(e.summary_json or {}), "live_calls": e.live_calls, "failure_category": e.failure_category,
                "created_at": _iso(e.created_at), "finished_at": _iso(e.finished_at)}

    @staticmethod
    def _approval_view(a: APR, s) -> dict:
        def email(uid):
            u = s.get(User, uid) if uid else None
            return u.email if u else None
        v = s.get(V, a.config_version_id)
        return {"public_id": a.public_id, "version_ref": v.public_id if v else None, "content_hash": a.config_hash, "status": a.status,
                "requested_by_email": email(a.requested_by_user_id), "requested_at": _iso(a.requested_at),
                "decided_by_email": email(a.decided_by_user_id), "decided_at": _iso(a.decided_at), "reason": a.reason}

    @staticmethod
    def _activation_view(a: ACT, s) -> dict:
        v = s.get(V, a.config_version_id) if a.config_version_id else None
        u = s.get(User, a.activated_by_user_id) if a.activated_by_user_id else None
        return {"public_id": a.public_id, "environment": a.environment, "kind": a.kind, "version_ref": v.public_id if v else None,
                "version": v.version if v else None, "content_hash": a.config_hash, "activated_by_email": u.email if u else None,
                "activated_at": _iso(a.activated_at), "deactivated_at": _iso(a.deactivated_at), "reason": a.reason, "open": a.deactivated_at is None}

    def list_versions(self, *, state: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if state:
            from src.persistence import AI_CONFIG_STATES
            if state not in AI_CONFIG_STATES:
                raise AIValidationError("Unknown state.")
            conds.append(V.state == state)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(V).where(*conds)) or 0
            rows = s.scalars(select(V).where(*conds).order_by(V.version.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._version_view(v, s) for v in rows], "total": total, "page": page, "page_size": page_size}

    def get_version(self, public_id: str) -> dict:
        with self._sf() as s:
            return self._version_view(self._load(s, public_id), s, detail=True)

    def _load(self, s, public_id: str) -> V:
        v = s.scalar(select(V).where(V.public_id == public_id))
        if v is None:
            raise AINotFound(public_id)
        return v

    # ------------------------------------------------------------------ draft
    def create_draft(self, *, name, notes, config, base_version_id: str | None, actor_user_id: int, audit: dict | None = None) -> dict:
        name = _text(name, "A name", MAX_NAME, required=True)
        notes = _text(notes or "", "Notes", MAX_NOTES, required=False)
        try:
            with self._sf() as s:
                base = self._load(s, base_version_id) if base_version_id else None
                source = config if config is not None else (dict(base.config_json) if base else K.baseline_config())
                canonical = self._canonical(source)
                nxt = (s.scalar(select(func.max(V.version))) or 0) + 1
                v = V(public_id=uuid.uuid4().hex, version=nxt, name=name, notes=notes, state="draft", config_json=canonical,
                      config_hash=K.config_hash(canonical), catalogue_version=C.CATALOGUE_VERSION, schema_version=K.SCHEMA_VERSION,
                      base_version_id=base.id if base else None, created_by_user_id=actor_user_id, created_at=self._clock())
                s.add(v)
                s.flush()
                _stage(s, {**audit, "target_id": v.public_id} if audit else None, config_version=v.version, config_hash=v.config_hash, new_state="draft")
                s.commit()
                return self._version_view(v, s, detail=True)
        except IntegrityError:
            raise AIConflict("Another version was created at the same time; retry.")

    @staticmethod
    def _canonical(raw: Any) -> dict:
        try:
            return K.normalise(raw)
        except K.ConfigError as exc:
            raise AIValidationError(str(exc))

    def update_draft(self, public_id: str, *, name=None, notes=None, config=None, actor_user_id: int, audit: dict | None = None) -> dict:
        with self._sf() as s:
            v = self._load(s, public_id)
            if v.state not in EDITABLE:
                raise AIConflict("Only a draft can be edited. Create a new version from this one instead.")
            old_hash = v.config_hash
            if name is not None:
                v.name = _text(name, "A name", MAX_NAME, required=True)
            if notes is not None:
                v.notes = _text(notes, "Notes", MAX_NOTES, required=False)
            if config is not None:
                v.config_json = self._canonical(config)
                v.config_hash = K.config_hash(v.config_json)
                v.validation_json = None
            _stage(s, {**audit, "target_id": v.public_id} if audit else None, config_version=v.version, old_hash=old_hash, config_hash=v.config_hash)
            s.commit()
            return self._version_view(v, s, detail=True)

    # ------------------------------------------------------------------ validate
    def validate(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        with self._sf() as s:
            v = self._load(s, public_id)
            if v.state != "draft":
                raise AIConflict("Only a draft can be validated; later states are already frozen.")
            canonical = self._canonical(v.config_json)
            if K.config_hash(canonical) != v.config_hash:
                raise AIConflict("The stored hash does not match the content.")
            checks = K.validate(canonical)
            ok = K.passed(checks)
            v.validation_json = {"passed": ok, "checks": [c.as_dict() for c in checks], "at": self._clock().isoformat()}
            if ok:
                v.state, v.validated_at = "validated", self._clock()
            _stage(s, {**audit, "target_id": v.public_id} if audit else None, config_version=v.version, config_hash=v.config_hash,
                   new_state=v.state, failed_checks=sum(1 for c in checks if not c.passed))
            s.commit()
            return self._version_view(v, s, detail=True)

    # ------------------------------------------------------------------ evaluate
    def request_evaluation(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        if self._jobs is None:
            raise AIConflict("The job queue is unavailable.")
        with self._sf() as s:
            v = self._load(s, public_id)
            if v.state not in ("validated", "evaluation_failed", "evaluated"):
                raise AIConflict("Validate the configuration before evaluating it.")
            if s.scalar(select(EV.id).where(EV.config_version_id == v.id, EV.status.in_(("queued", "running")))):
                raise AIConflict("An evaluation is already queued or running for this version.")
            e = EV(public_id=uuid.uuid4().hex, config_version_id=v.id, config_hash=v.config_hash, evaluator_version=EVALUATOR_VERSION, status="queued",
                   requested_by_user_id=actor_user_id, created_at=self._clock())
            s.add(e)
            s.flush()
            _stage(s, {**audit, "target_id": e.public_id} if audit else None, config_version=v.version, config_hash=v.config_hash, evaluation_public_id=e.public_id,
                   new_state="queued")
            s.commit()
            ev_pid = e.public_id
        try:
            self._jobs.enqueue(JOB_EVALUATE, {"evaluation_id": ev_pid}, idempotency_key=f"ai-eval:{ev_pid}", actor_user_id=actor_user_id)
        except Exception:
            with self._sf() as s:
                s.execute(update(EV).where(EV.public_id == ev_pid, EV.status == "queued").values(status="error", failure_category="enqueue_failed", finished_at=self._clock()))
                s.commit()
            raise AIConflict("The evaluation could not be queued.")
        with self._sf() as s:
            return self._eval_view(s.scalar(select(EV).where(EV.public_id == ev_pid)))

    def run_evaluation(self, evaluation_public_id: str) -> str:
        """Worker entry point. Idempotent: a terminal evaluation is a no-op. Returns the final status."""
        with self._sf() as s:
            e = s.scalar(select(EV).where(EV.public_id == evaluation_public_id))
            if e is None:
                raise AINotFound(evaluation_public_id)
            if e.status in ("passed", "failed", "error"):
                return e.status
            e.status = "running"
            v = s.get(V, e.config_version_id)
            s.commit()
        with self._sf() as s:
            e = s.scalar(select(EV).where(EV.public_id == evaluation_public_id))
            v = s.get(V, e.config_version_id)
            try:
                canonical = K.normalise(v.config_json)
                if K.config_hash(canonical, v.catalogue_version) != v.config_hash or v.config_hash != e.config_hash:
                    result, status, category = None, "error", "hash_mismatch"
                elif v.catalogue_version != C.CATALOGUE_VERSION:
                    result, status, category = None, "error", "catalogue_changed"
                else:
                    result = evaluate(canonical)
                    status, category = ("passed" if result["passed"] else "failed"), None
            except Exception:  # noqa: BLE001 - a fixed category, never the exception text
                result, status, category = None, "error", "evaluation_error"
            now = self._clock()
            e.status, e.failure_category, e.finished_at = status, category, now
            if result is not None:
                e.checks_json, e.summary_json, e.live_calls = result["checks"], result["summary"], int(result["live_calls"])
            if status in ("passed", "failed") and v.state in ("validated", "evaluation_failed", "evaluated") and v.config_hash == e.config_hash:
                v.state = "evaluated" if status == "passed" else "evaluation_failed"
            _stage(s, A.build_audit(event_type=A.ADMIN_AI_EVALUATION_COMPLETED, actor_user_id=None, request_id=None, target_type="ai_config_evaluation",
                                    target_id=e.public_id, result="success" if status == "passed" else "failure"),
                   config_version=v.version, config_hash=e.config_hash, evaluation_public_id=e.public_id, new_state=status)
            s.commit()
            return status

    # ------------------------------------------------------------------ approval
    def _passed_evaluation(self, s, v: V) -> EV:
        """The latest evaluation, only if it passed, was made by the CURRENT evaluator and is bound to this exact hash."""
        e = s.scalar(select(EV).where(EV.config_version_id == v.id).order_by(EV.id.desc()))
        if e is None or e.status != "passed" or e.live_calls != 0:
            raise AIConflict("The latest evaluation has not passed. A configuration cannot be approved or activated without a passed evaluation.")
        if e.config_hash != v.config_hash or K.config_hash(K.normalise(v.config_json), v.catalogue_version) != v.config_hash:
            raise AIConflict("The evaluation does not match the configuration content.")
        if e.evaluator_version != EVALUATOR_VERSION or v.catalogue_version != C.CATALOGUE_VERSION:
            raise AIConflict("The evaluation is out of date (evaluator or catalogue changed). Evaluate again.")
        return e

    def request_approval(self, public_id: str, *, reason, actor_user_id: int, audit: dict | None = None) -> dict:
        reason = _text(reason, "A reason", MAX_REASON, required=True)
        with self._sf() as s:
            v = self._load(s, public_id)
            if v.state != "evaluated":
                raise AIConflict("Only a configuration with a passed evaluation can be submitted for approval.")
            e = self._passed_evaluation(s, v)
            a = APR(public_id=uuid.uuid4().hex, config_version_id=v.id, config_hash=v.config_hash, evaluation_id=e.id, status="pending",
                    requested_by_user_id=actor_user_id, requested_at=self._clock(), reason=reason)
            s.add(a)
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise AIConflict("An approval is already pending for this version.")
            _stage(s, {**audit, "target_id": a.public_id} if audit else None, config_version=v.version, config_hash=v.config_hash,
                   approval_public_id=a.public_id, evaluation_public_id=e.public_id, new_state="pending")
            s.commit()
            return self._approval_view(a, s)

    def decide_approval(self, approval_public_id: str, *, approve: bool, reason, actor_user_id: int, audit: dict | None = None) -> dict:
        reason = _text(reason, "A reason", MAX_REASON, required=True)
        with self._sf() as s:
            a = s.scalar(select(APR).where(APR.public_id == approval_public_id))
            if a is None:
                raise AINotFound(approval_public_id)
            if a.status != "pending":
                raise AIConflict("This request has already been decided.")
            v = s.get(V, a.config_version_id)
            if a.requested_by_user_id is not None and a.requested_by_user_id == actor_user_id:
                raise AIForbidden("A different administrator must decide this request: you cannot approve a request you made.")
            if v.created_by_user_id is not None and v.created_by_user_id == actor_user_id:
                raise AIForbidden("A different administrator must decide this request: you cannot approve a configuration you authored.")
            u = s.get(User, actor_user_id)
            if u is None or u.status != ACCOUNT_STATUS_ACTIVE or perm.AI_ACTIVATE not in perm.permissions_for_role(u.platform_role):
                raise AIForbidden("The approver must be an active administrator with the AI activation permission.")
            if approve:
                if v.state != "evaluated" or a.config_hash != v.config_hash:
                    raise AIConflict("The configuration changed or is no longer awaiting approval.")
                self._passed_evaluation(s, v)
            a.status, a.decided_by_user_id, a.decided_at, a.reason = ("approved" if approve else "rejected"), actor_user_id, self._clock(), reason
            if approve:
                v.state = "approved"
            elif v.state == "evaluated":
                v.state = "rejected"
            _stage(s, {**audit, "target_id": a.public_id} if audit else None, config_version=v.version, config_hash=v.config_hash,
                   approval_public_id=a.public_id, old_state="pending", new_state=a.status)
            s.commit()
            return self._approval_view(a, s)

    # ------------------------------------------------------------------ activation
    def _open(self, s, environment: str) -> ACT | None:
        return s.scalar(select(ACT).where(ACT.environment == environment, ACT.deactivated_at.is_(None)))

    def _verify_activatable(self, s, v: V) -> APR:
        """Re-derive EVERY activation precondition from stored facts. This is the single gate; nothing else activates a configuration."""
        if v.state != "approved":
            raise AIConflict("Only an approved configuration can be activated.")
        self._passed_evaluation(s, v)
        a = s.scalar(select(APR).where(APR.config_version_id == v.id, APR.status == "approved").order_by(APR.id.desc()))
        if a is None or a.config_hash != v.config_hash or a.decided_by_user_id is None:
            raise AIConflict("There is no second approval for this exact configuration.")
        if a.decided_by_user_id == v.created_by_user_id or a.decided_by_user_id == a.requested_by_user_id:
            raise AIForbidden("The approval does not satisfy the distinct second approver rule.")
        return a

    def _target(self) -> str:
        """The ONLY environment this process may activate: its own. An unrecognised API_ENV disables governed activation (fail closed)."""
        if self.environment not in ENVIRONMENTS:
            raise AIConflict("Governed activation is disabled: this deployment's environment is not recognised (development, staging or production).")
        return self.environment

    def activate(self, public_id: str, *, reason, actor_user_id: int, audit: dict | None = None) -> dict:
        environment = self._target()
        reason = _text(reason, "A reason", MAX_REASON, required=True)
        now = self._clock()
        with self._sf() as s:
            v = self._load(s, public_id)
            approval = self._verify_activatable(s, v)
            if environment == "production" and not s.scalar(select(ACT.id).where(ACT.environment == "staging", ACT.config_version_id == v.id,
                                                                                  ACT.config_hash == v.config_hash)):
                raise AIConflict("Activate this exact version in staging first. Production activation requires a prior STAGING activation of the same "
                                 "content hash (a development activation does not count).")
            current = self._open(s, environment)
            if current is not None and current.config_version_id == v.id:
                raise AIConflict("This version is already active in that environment.")
            self._swap(s, environment, current, v, kind="activate", approval=approval, actor=actor_user_id, reason=reason, now=now, audit=audit)
            return self._commit_activation(s, environment, v)

    def _swap(self, s, environment: str, current: ACT | None, v: V | None, *, kind: str, approval: APR | None, actor: int, reason: str, now: datetime,
              audit: dict | None) -> ACT:
        if current is not None:
            current.deactivated_at = now
            s.flush()                                    # close first so the one-open-per-environment index never conflicts
        row = ACT(public_id=uuid.uuid4().hex, environment=environment, config_version_id=v.id if v else None, config_hash=v.config_hash if v else None,
                  kind=kind, approval_id=approval.id if approval else None, activated_by_user_id=actor, activated_at=now, reason=reason)
        s.add(row)
        s.flush()
        _stage(s, {**audit, "target_id": row.public_id} if audit else None, environment=environment, config_version=v.version if v else None,
               config_hash=v.config_hash if v else None, previous_activation_public_id=current.public_id if current else None,
               old_state="active" if current else "code_defaults", new_state="active" if v else "code_defaults")
        return row

    def _commit_activation(self, s, environment: str, v: V | None) -> dict:
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise AIConflict("The active configuration changed while this ran; reload and retry.")
        if self._resolver is not None:
            self._resolver.invalidate()
        row = self._open(s, environment)
        return self._activation_view(row, s)

    def rollback(self, *, to_code: bool, reason, actor_user_id: int, audit: dict | None = None) -> dict:
        """Return an environment to its previous activated version, or to the code-defined defaults. Needs no new approval: only a version that
        was already approved and activated there can be restored, and it is re-verified like any activation."""
        environment = self._target()
        reason = _text(reason, "A reason", MAX_REASON, required=True)
        now = self._clock()
        with self._sf() as s:
            current = self._open(s, environment)
            if current is None or current.config_version_id is None:
                raise AIConflict("Nothing is active in that environment, so there is nothing to roll back.")
            if to_code:
                self._swap(s, environment, current, None, kind="revert_to_code", approval=None, actor=actor_user_id, reason=reason, now=now, audit=audit)
                return self._commit_activation(s, environment, None)
            prior = s.scalar(select(ACT).where(ACT.environment == environment, ACT.id != current.id, ACT.config_version_id.is_not(None),
                                               ACT.config_version_id != current.config_version_id).order_by(ACT.id.desc()))
            if prior is None:
                raise AIConflict("There is no earlier activation to return to. Revert to the code defaults instead.")
            v = s.get(V, prior.config_version_id)
            if v.state != "approved":
                raise AIConflict("The earlier configuration is no longer eligible (retired or changed). Revert to the code defaults instead.")
            approval = self._verify_activatable(s, v)
            self._swap(s, environment, current, v, kind="rollback", approval=approval, actor=actor_user_id, reason=reason, now=now, audit=audit)
            return self._commit_activation(s, environment, v)

    def retire(self, public_id: str, *, reason, actor_user_id: int, audit: dict | None = None) -> dict:
        reason = _text(reason, "A reason", MAX_REASON, required=True)
        with self._sf() as s:
            v = self._load(s, public_id)
            if v.state == "retired":
                raise AIConflict("This version is already retired.")
            if s.scalar(select(ACT.id).where(ACT.config_version_id == v.id, ACT.deactivated_at.is_(None))):
                raise AIConflict("An active version cannot be retired. Activate another version or revert to the code defaults first.")
            old = v.state
            v.state, v.retired_at = "retired", self._clock()
            _stage(s, {**audit, "target_id": v.public_id} if audit else None, config_version=v.version, config_hash=v.config_hash, old_state=old,
                   new_state="retired", reason=reason)
            s.commit()
            return self._version_view(v, s)

    # ------------------------------------------------------------------ environments / history
    def environments(self) -> dict:
        from src.ai_admin.resolver import resolve_profiles_for

        out = []
        with self._sf() as s:
            for env in ENVIRONMENTS:
                row = self._open(s, env)
                v = s.get(V, row.config_version_id) if row and row.config_version_id else None
                out.append({"environment": env, "mode": "governed" if v else "code_defaults",
                            "active": self._activation_view(row, s) if row else None,
                            "version": self._version_view(v, s) if v else None,
                            "profiles": resolve_profiles_for(v.config_json if v else None)})
        return {"items": out, "this_environment": self.environment or "unsupported",
                "note": "This server activates only its own environment. With nothing active an environment uses the code-defined registry (environment overrides, then code defaults)."}

    def history(self, *, environment: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if environment:
            if environment not in ENVIRONMENTS:
                raise AIValidationError("Unknown environment.")
            conds.append(ACT.environment == environment)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(ACT).where(*conds)) or 0
            rows = s.scalars(select(ACT).where(*conds).order_by(ACT.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._activation_view(a, s) for a in rows], "total": total, "page": page, "page_size": page_size}

    def list_approvals(self, *, status: str | None = None, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if status:
            from src.persistence import AI_APPROVAL_STATUSES
            if status not in AI_APPROVAL_STATUSES:
                raise AIValidationError("Unknown status.")
            conds.append(APR.status == status)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(APR).where(*conds)) or 0
            rows = s.scalars(select(APR).where(*conds).order_by(APR.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._approval_view(a, s) for a in rows], "total": total, "page": page, "page_size": page_size}

    def stats(self) -> dict:
        with self._sf() as s:
            by_state = dict(s.execute(select(V.state, func.count()).group_by(V.state)).all())
            pending = s.scalar(select(func.count()).select_from(APR).where(APR.status == "pending")) or 0
            active = {env: (self._open(s, env) is not None) for env in ENVIRONMENTS}
        return {"versions": sum(by_state.values()), "by_state": by_state, "pending_approvals": pending, "active": active}
