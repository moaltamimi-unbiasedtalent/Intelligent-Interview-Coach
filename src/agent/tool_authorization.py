"""Server-side authorization of every model-requested tool call (01D, REVIEW-01 R4 and R5, PG-03).

The model proposes; the server decides. Immediately before any registered tool's handler can run,
:class:`ToolAuthorizer` evaluates ONE deterministic, default-deny decision over facts that come from the
server (the run state, the registry, the code-defined policy table), never from the model's output:

* the authenticated user (``RunAuthContext.user_id``, from the run, never from tool arguments);
* the user's own words for the run (the goal and later user turns) against each tool's declared intent;
* the tool's declared permission and side-effect class (read-only / state-proposing / external access);
* the argument shape and bounds (the tool's Pydantic model plus global size, depth and type-confusion
  limits; unknown fields are refused, never silently dropped);
* ownership of every referenced resource id (none of today's tools takes one; the check is enforced for
  any tool that declares one, and a missing proof is a refusal);
* the run state (cancelled, expired), a per-run call budget, a per-step call cap and a repeated-call limit;
* the injection risk of the context that led to the call (``RetrievalResult.injection_risk`` and the
  01A quarantine, summarised by the retrieval tool into ``untrusted_context``) and whether an argument was
  copied from untrusted text rather than from the user.

A refusal produces NO side effect (the handler is never reached), one audit record carrying only
identifiers and a reason code (never an argument value, never user text), and a generic structured result
for the model that names no policy text and no other user's data.

This module imports no provider, database or UI code and makes no network call.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ValidationError

__all__ = [
    "SideEffect", "ToolPolicy", "RunAuthContext", "AuthorizationDecision", "ToolAuthorizer",
    "ToolAuthorizationDenied", "DEFAULT_POLICIES", "Reason", "public_denial",
    "MAX_TOOL_CALLS_PER_RUN", "MAX_TOOL_CALLS_PER_STEP", "MAX_IDENTICAL_CALLS_PER_RUN",
    "MAX_ARGS_JSON_CHARS", "AUDIT_TRAIL_MAX", "FINGERPRINT_TRAIL_MAX",
    "bounded_append", "build_run_context", "schema_fingerprint", "call_fingerprint",
]

_LOG = logging.getLogger("ask4mo.agent.tool_authorization")

# --- limits (server constants; not model-visible) ---------------------------------------------------------
MAX_TOOL_CALLS_PER_RUN = 60          # every attempted call counts, allowed or refused (thread lifetime)
MAX_TOOL_CALLS_PER_STEP = 8          # calls the model may batch into one tools step
MAX_IDENTICAL_CALLS_PER_RUN = 3      # same tool and same canonical arguments (loop guard)
MAX_ARGS_JSON_CHARS = 40_000         # total serialised arguments (the largest tool field is 12 000 chars)
MAX_ARG_STRING_CHARS = 20_000
MAX_ARG_COLLECTION_ITEMS = 100
MAX_ARG_DEPTH = 5
AUDIT_TRAIL_MAX = 200
FINGERPRINT_TRAIL_MAX = 200
_UNTRUSTED_RISK_WARN = 0.5           # a retrieval whose highest chunk risk reaches this makes the run "tainted"


class SideEffect(str, Enum):
    """What a tool can do, as declared in code. The model cannot change it."""

    READ_ONLY = "read_only"              # reads governed knowledge or computes; no state change, no egress
    STATE_PROPOSING = "state_proposing"  # asks for a state change that a human must approve (memory, handoff)
    EXTERNAL = "external"                # reaches outside the platform (provider or web egress)


class Reason(str, Enum):
    """Internal reason codes (audit only). The model only ever sees :func:`public_denial`."""

    ALLOWED = "allowed"
    RUN_NOT_ACTIVE = "run_not_active"
    TOOL_NOT_REGISTERED = "tool_not_registered"
    TOOL_DISABLED = "tool_disabled"
    NO_POLICY = "no_policy"
    SCHEMA_CHANGED = "schema_changed"
    ARGUMENTS_TOO_LARGE = "arguments_too_large"
    ARGUMENTS_NOT_OBJECT = "arguments_not_object"
    UNKNOWN_ARGUMENT = "unknown_argument"
    INVALID_ARGUMENTS = "invalid_arguments"
    TYPE_CONFUSION = "type_confusion"
    BUDGET_EXHAUSTED = "budget_exhausted"
    STEP_CALL_LIMIT = "step_call_limit"
    REPEATED_CALL = "repeated_call"
    IDENTITY_REQUIRED = "identity_required"
    PERMISSION_DENIED = "permission_denied"
    OWNERSHIP_UNPROVEN = "ownership_unproven"
    RESOURCE_NOT_OWNED = "resource_not_owned"
    NO_USER_GOAL = "no_user_goal"
    ARGUMENT_FROM_UNTRUSTED_CONTEXT = "argument_from_untrusted_context"
    UNTRUSTED_DESTINATION = "untrusted_destination"
    GOAL_DOES_NOT_COVER = "goal_does_not_cover"
    DECISION_MISMATCH = "decision_mismatch"


# Reasons the model is told about, mapped to a coarse public code. Anything not listed is "not_permitted".
_PUBLIC_CODE: dict[Reason, str] = {
    Reason.TOOL_NOT_REGISTERED: "not_available",
    Reason.TOOL_DISABLED: "not_available",
    Reason.INVALID_ARGUMENTS: "invalid_arguments",
    Reason.ARGUMENTS_NOT_OBJECT: "invalid_arguments",
    Reason.ARGUMENTS_TOO_LARGE: "invalid_arguments",
    Reason.UNKNOWN_ARGUMENT: "invalid_arguments",
    Reason.TYPE_CONFUSION: "invalid_arguments",
    Reason.BUDGET_EXHAUSTED: "limit_reached",
    Reason.STEP_CALL_LIMIT: "limit_reached",
    Reason.REPEATED_CALL: "limit_reached",
    Reason.RUN_NOT_ACTIVE: "run_not_active",
}
_PUBLIC_MESSAGE = {
    "not_available": "This tool is not available.",
    "invalid_arguments": "The tool call arguments were not accepted.",
    "limit_reached": "The tool call limit for this request was reached.",
    "run_not_active": "This request is no longer active.",
    "not_permitted": "This tool call was not permitted.",
}


def public_denial(reason: Reason) -> dict[str, str]:
    """The ONLY thing the model is told about a refusal: a fixed message and a coarse code.

    It never carries argument content, resource ids, another user's data or any policy text.
    """
    code = _PUBLIC_CODE.get(reason, "not_permitted")
    return {"error": _PUBLIC_MESSAGE[code], "code": code}


class ToolAuthorizationDenied(Exception):
    """Raised by the registry when a call is refused; carries the decision (no argument content)."""

    def __init__(self, decision: "AuthorizationDecision") -> None:
        super().__init__(f"tool call denied: {decision.reason.value}")
        self.decision = decision


# --- policy table -----------------------------------------------------------------------------------------

PERM_READ = "agent.tool.read"
PERM_OWNER_DATA = "agent.tool.owner_data"
PERM_PROPOSE = "agent.tool.propose"
PERM_EXTERNAL = "agent.tool.external"
_AUTHENTICATED_PERMISSIONS = frozenset({PERM_READ, PERM_OWNER_DATA, PERM_PROPOSE, PERM_EXTERNAL})
_ANONYMOUS_PERMISSIONS = frozenset({PERM_READ})


@dataclass(frozen=True)
class ToolPolicy:
    """Declared, code-owned facts about one tool. Never derived from model output."""

    name: str
    side_effect: SideEffect
    permission: str = PERM_READ
    owner_scoped: bool = False          # reads or acts on the signed-in user's private data
    # Tool argument -> resource type. Ownership of every value MUST be proven by a verifier.
    resource_args: Mapping[str, str] = field(default_factory=dict)
    # Intent the user's own words must cover when the call is tainted (None = no intent lexicon).
    intent: str | None = None
    # The tool's RESULT carries text from outside the user's own input (retrieved, web, candidate documents).
    result_untrusted: bool = False


DEFAULT_POLICIES: dict[str, ToolPolicy] = {p.name: p for p in (
    ToolPolicy("AnalyzeJobDescription", SideEffect.READ_ONLY),
    ToolPolicy("AnalyzeCandidateGaps", SideEffect.READ_ONLY),
    ToolPolicy("BuildPreparationPlan", SideEffect.READ_ONLY),
    ToolPolicy("GenerateInterviewQuestions", SideEffect.READ_ONLY),
    ToolPolicy("SearchCareerKnowledge", SideEffect.READ_ONLY, result_untrusted=True),
    ToolPolicy("ResearchCurrentMarket", SideEffect.EXTERNAL, permission=PERM_EXTERNAL, intent="market",
               result_untrusted=True),
    ToolPolicy("AnalyzeRoleOpportunity", SideEffect.READ_ONLY),
    ToolPolicy("FindCandidateEvidence", SideEffect.READ_ONLY, permission=PERM_OWNER_DATA, owner_scoped=True,
               result_untrusted=True),
    ToolPolicy("BuildCoachingStrategy", SideEffect.READ_ONLY),
    ToolPolicy("ProposePreparationMemory", SideEffect.STATE_PROPOSING, permission=PERM_PROPOSE,
               owner_scoped=True, intent="memory"),
    ToolPolicy("RequestPracticeHandoff", SideEffect.STATE_PROPOSING, permission=PERM_PROPOSE,
               owner_scoped=True, intent="handoff"),
)}

# --- text helpers -----------------------------------------------------------------------------------------

_NON_WORD = re.compile(r"\W+", re.UNICODE)
_URLISH = re.compile(r"(://|\bwww\.|@|\b[a-z0-9-]+\.(?:com|net|org|io|dev|test|de|fr|es|it|pt|nl|uk|us)\b)", re.I)


def _norm(text: str) -> str:
    """Case-folded, accent-stripped, punctuation-collapsed form used only for matching."""
    folded = unicodedata.normalize("NFKD", str(text)).casefold()
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return _NON_WORD.sub(" ", stripped).strip()


# Word-prefix lexicons per intent (en, de, fr, es, it, pt, nl), matched on the normalised user text.
_INTENT_TERMS: dict[str, tuple[str, ...]] = {
    "memory": (
        "remember", "save", "note ", "keep", "store", "memor",
        "merk", "speicher", "notier", "behalt",
        "souvien", "retenir", "retiens", "enregistr", "sauvegard", "memoris", "garde",
        "recuerd", "guard", "anot", "memoriz",
        "ricord", "salva", "memorizz", "annot",
        "lembr", "salv",
        "onthoud", "bewaar", "noteer", "opslaan", "sla op",
    ),
    "handoff": (
        "practice", "practise", "mock", "rehears", "simulat", "start the interview", "interview practice",
        "uben", "ube ", "probe", "trainier", "simulier", "ubungs",
        "pratiqu", "entrain", "simul", "exerc", "repet",
        "practic", "ensay", "entren",
        "eserc", "pratic", "allen", "prova",
        "ensai", "trein",
        "oefen", "train",
    ),
    "market": (
        "current", "latest", "today", "now", "recent", "salar", "pay ", "vacanc", "opening", "hiring",
        "job market", "company", "website", "jobs", "advertis",
        "aktuell", "heute", "gehalt", "stellen", "offene", "einstell", "arbeitsmarkt", "unternehmen", "firma",
        "actuel", "aujourd", "salaire", "offre", "recrut", "marche", "entreprise",
        "actual", "hoy", "salario", "vacante", "oferta", "contrat", "mercado", "empresa",
        "attual", "oggi", "stipendio", "offert", "assun", "mercato", "azienda",
        "atual", "hoje", "vaga", "contrata",
        "actueel", "huidige", "vandaag", "salaris", "vacature", "aanwerv", "bedrijf",
    ),
}


def _covers(intent: str | None, user_text_norm: str) -> bool:
    """True when the user's own words explicitly mention the tool's intent (word-prefix match)."""
    if intent is None:
        return True
    padded = " " + user_text_norm + " "
    return any((" " + t) in padded for t in _INTENT_TERMS.get(intent, ()))


_IDENTITY_TOKENS = frozenset({
    "id", "ids", "uid", "uuid", "user", "users", "owner", "owners", "account", "accounts", "email", "tenant", "workspace",
    "session", "token", "subject", "sub", "userid", "ownerid", "accountid", "documentid", "storyid", "memoryid",
    "interviewid", "opportunityid", "sessionid", "runid", "threadid", "tenantid", "workspaceid", "claimid"})
MAX_UNKNOWN_ARGUMENTS = 5


def _identity_like(key: str) -> bool:
    """True for an undeclared argument name that looks like an identity or resource reference (user_id, ownerId, ...)."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key)).lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", spaced) if t]
    return any(t in _IDENTITY_TOKENS for t in tokens) or "".join(tokens) in _IDENTITY_TOKENS


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _value_strings(value: Any, depth: int = 0) -> list[str]:
    """All string leaves of an argument value (bounded; arguments are already size-checked)."""
    if isinstance(value, str):
        return [value]
    if depth >= MAX_ARG_DEPTH:
        return []
    out: list[str] = []
    if isinstance(value, Mapping):
        for v in value.values():
            out.extend(_value_strings(v, depth + 1))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(_value_strings(v, depth + 1))
    return out


def _derived_from_untrusted(arg_strings: list[str], trusted_norm: str, untrusted_norm: str) -> tuple[bool, bool]:
    """(derived, destination_like): was an argument copied from untrusted text and NOT from the user?

    A value is derived when a normalised window of it appears verbatim in untrusted text but nowhere in
    the user's own text. Short plain values (a country code, a skill word) are ignored; URL, host or
    e-mail like values are always tested because they are the egress channel of an injected instruction.
    """
    if not untrusted_norm:
        return False, False
    derived = destination = False
    t_padded, u_padded = " " + trusted_norm + " ", " " + untrusted_norm + " "
    for raw in arg_strings:
        norm = _norm(raw)
        if not norm:
            continue
        url_like = bool(_URLISH.search(raw))
        tokens = norm.split()
        if url_like:
            windows = [norm]
        elif len(tokens) >= 5:
            windows = [" ".join(tokens[i:i + 5]) for i in range(0, len(tokens) - 4)]
        elif len(norm) >= 14:
            windows = [norm]
        else:
            continue
        hit = any((" " + w + " ") in u_padded and (" " + w + " ") not in t_padded for w in windows)
        if hit:
            derived = True
            destination = destination or url_like
    return derived, destination


# --- fingerprints -----------------------------------------------------------------------------------------


def schema_fingerprint(args_model: type[BaseModel]) -> str:
    """SHA-256 of the tool's JSON schema: detects an argument schema that changed after registration."""
    return hashlib.sha256(json.dumps(args_model.model_json_schema(), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _canonical_args(raw_args: Any) -> str:
    return json.dumps(raw_args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def call_fingerprint(name: str, raw_args: Any) -> str:
    """Stable 16-hex digest of a call (tool + canonical arguments). Held in run state only (loop guard
    and decision binding); it is never written to the audit trail."""
    try:
        body = _canonical_args(raw_args if raw_args is not None else {})
    except (TypeError, ValueError, RecursionError):
        body = "unserialisable"
    return hashlib.sha256(f"{name}\n{body}".encode("utf-8")).hexdigest()[:16]


# --- context and decision ---------------------------------------------------------------------------------


@dataclass
class RunAuthContext:
    """Everything the decision may use, built by the SERVER from run state (see :func:`build_run_context`)."""

    run_id: str | None = None
    user_id: str | None = None
    step: int = 0
    user_text: str = ""                    # the user's own words for the run (goal and later user turns)
    untrusted_text: str = ""               # untrusted-result tool output, JD and background
    approved_text: str = ""                # the user's own approved saved memory: data, but never a stranger's text
    calls_made: int = 0                    # attempted calls so far this run (allowed or refused)
    calls_in_step: int = 0
    seen_fingerprints: tuple[str, ...] = ()
    max_injection_risk: float = 0.0
    quarantined_chunks: int = 0
    disabled_tools: frozenset[str] = frozenset()
    cancelled: bool = False
    control_required: bool = False
    expired: bool = False
    granted_permissions: frozenset[str] | None = None   # None = derive from the identity


@dataclass(frozen=True)
class AuthorizationDecision:
    """One decision. ``to_audit`` is the only serialisation that may be stored or logged."""

    allowed: bool
    reason: Reason
    tool: str                    # a registered tool name, or "unregistered"
    side_effect: str | None
    run_id: str | None
    step: int
    call_index: int
    fingerprint: str             # binds the decision to one call; never audited
    tainted: bool = False

    def to_audit(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "step": self.step, "call_index": self.call_index, "tool": self.tool,
                "side_effect": self.side_effect, "allowed": self.allowed, "reason": self.reason.value,
                "tainted": self.tainted}

    def matches(self, name: str, raw_args: Any) -> bool:
        return self.fingerprint == call_fingerprint(name, raw_args)


OwnershipVerifier = Callable[[str, Any, str], bool]
AuditSink = Callable[[dict[str, Any]], None]


def _json_depth_and_shape_ok(value: Any, depth: int = 0) -> Reason | None:
    """Bounds on the raw (pre-validation) argument tree: depth, collection size, string size, JSON types only."""
    if depth > MAX_ARG_DEPTH:
        return Reason.ARGUMENTS_TOO_LARGE
    if value is None or isinstance(value, (bool, int, float)):
        return None
    if isinstance(value, str):
        return Reason.ARGUMENTS_TOO_LARGE if len(value) > MAX_ARG_STRING_CHARS else None
    if isinstance(value, Mapping):
        if len(value) > MAX_ARG_COLLECTION_ITEMS:
            return Reason.ARGUMENTS_TOO_LARGE
        for k, v in value.items():
            if not isinstance(k, str):
                return Reason.INVALID_ARGUMENTS
            bad = _json_depth_and_shape_ok(v, depth + 1)
            if bad:
                return bad
        return None
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ARG_COLLECTION_ITEMS:
            return Reason.ARGUMENTS_TOO_LARGE
        for v in value:
            bad = _json_depth_and_shape_ok(v, depth + 1)
            if bad:
                return bad
        return None
    return Reason.INVALID_ARGUMENTS   # bytes, sets, objects: not JSON, never a legitimate model argument


class ToolAuthorizer:
    """Default-deny, pure decision function plus an audit sink. Holds no per-run state."""

    def __init__(
        self,
        policies: Mapping[str, ToolPolicy] | None = None,
        *,
        ownership_verifiers: Mapping[str, OwnershipVerifier] | None = None,
        audit_sink: AuditSink | None = None,
        run_control: Callable[[str], str | None] | None = None,
    ) -> None:
        self._policies: dict[str, ToolPolicy] = dict(DEFAULT_POLICIES if policies is None else policies)
        self._verifiers: dict[str, OwnershipVerifier] = dict(ownership_verifiers or {})
        self._sink = audit_sink
        # Optional live probe (run_id -> "cancelled" | "expired" | None) so a durable cancellation or a
        # deadline kept OUTSIDE the in-flight graph state still stops execution (wired by 04C).
        self._run_control = run_control

    def set_run_control(self, probe) -> None:
        """Install the server-owned durable control probe (04C)."""
        self._run_control = probe

    def run_control(self, run_id: str | None, required: bool = False) -> str | None:
        """Read cancellation/deadline facts; a failed read stops execution."""
        value = self._run_control(run_id) if self._run_control and run_id else None
        if value in ("cancelled", "expired", "failed"):
            return value
        return "expired" if required and value is None else None

    # -- policy access ------------------------------------------------------------------------------------
    def policy_for(self, name: str) -> ToolPolicy | None:
        return self._policies.get(name)

    def add_policy(self, policy: ToolPolicy) -> None:
        self._policies[policy.name] = policy

    def policies(self) -> dict[str, ToolPolicy]:
        return dict(self._policies)

    # -- the decision -------------------------------------------------------------------------------------
    def decide(self, name: str, raw_args: Any, run: RunAuthContext, spec: Any | None) -> AuthorizationDecision:
        """Authorize ONE call. ``spec`` is the registry's ToolSpec (or None when the tool is unknown).

        Pure with respect to ``run``: counters come from the context, so deciding twice gives the same answer.
        """
        policy = self._policies.get(name) if isinstance(name, str) else None
        registered = spec is not None and isinstance(name, str)
        label = name if registered else "unregistered"
        fingerprint = call_fingerprint(name if isinstance(name, str) else "?", raw_args)
        side = policy.side_effect.value if policy else None

        def decision(allowed: bool, reason: Reason, tainted: bool = False) -> AuthorizationDecision:
            d = AuthorizationDecision(allowed=allowed, reason=reason, tool=label, side_effect=side, run_id=run.run_id,
                                      step=run.step, call_index=run.calls_made + run.calls_in_step,
                                      fingerprint=fingerprint, tainted=tainted)
            self._audit(d)
            return d

        # 1. run state
        try:
            probe = self.run_control(run.run_id, required=run.control_required)
        except Exception:
            return decision(False, Reason.RUN_NOT_ACTIVE)
        if run.cancelled or run.expired or probe in ("cancelled", "expired"):
            return decision(False, Reason.RUN_NOT_ACTIVE)
        # 2. registry membership and the per-run capability toggle
        if not registered:
            return decision(False, Reason.TOOL_NOT_REGISTERED)
        if name in run.disabled_tools:
            return decision(False, Reason.TOOL_DISABLED)
        # 3. a declared policy is mandatory
        if policy is None:
            return decision(False, Reason.NO_POLICY)
        # 4. the argument schema must be the one pinned at registration
        pinned = getattr(spec, "schema_sha", None)
        if pinned is None or schema_fingerprint(spec.args_model) != pinned:
            return decision(False, Reason.SCHEMA_CHANGED)
        # 5. raw argument shape and bounds (before any serialisation of an adversarial payload)
        args = {} if raw_args is None else raw_args
        if not isinstance(args, Mapping):
            return decision(False, Reason.ARGUMENTS_NOT_OBJECT)
        bad = _json_depth_and_shape_ok(args)
        if bad:
            return decision(False, bad)
        try:
            if len(_canonical_args(args)) > MAX_ARGS_JSON_CHARS:
                return decision(False, Reason.ARGUMENTS_TOO_LARGE)
        except (TypeError, ValueError, RecursionError):
            return decision(False, Reason.INVALID_ARGUMENTS)
        # 6. loop limits
        if run.calls_made >= MAX_TOOL_CALLS_PER_RUN:
            return decision(False, Reason.BUDGET_EXHAUSTED)
        if run.calls_in_step >= MAX_TOOL_CALLS_PER_STEP:
            return decision(False, Reason.STEP_CALL_LIMIT)
        if sum(1 for f in run.seen_fingerprints if f == fingerprint) >= MAX_IDENTICAL_CALLS_PER_RUN:
            return decision(False, Reason.REPEATED_CALL)
        # 7. identity and the tool's declared permission
        user = str(run.user_id).strip() if run.user_id is not None else ""
        granted = run.granted_permissions if run.granted_permissions is not None else (
            _AUTHENTICATED_PERMISSIONS if user else _ANONYMOUS_PERMISSIONS)
        if policy.owner_scoped and not user:
            return decision(False, Reason.IDENTITY_REQUIRED)
        if policy.permission not in granted:
            return decision(False, Reason.PERMISSION_DENIED)
        # 8. argument fields: unknown fields refused, types and bounds from the tool's own Pydantic model
        fields = set(spec.args_model.model_fields)
        unknown = [k for k in args if k not in fields]
        if unknown and (len(unknown) > MAX_UNKNOWN_ARGUMENTS or any(
                _identity_like(k) or not _is_scalar(args[k]) for k in unknown)):
            return decision(False, Reason.UNKNOWN_ARGUMENT)
        # A harmless undeclared scalar (a model that invents a field name) cannot influence execution: the tool's own
        # model ignores it, exactly as before this layer. Identity-like keys, structures and floods are refused above.
        try:
            validated = spec.args_model(**dict(args))
        except (ValidationError, TypeError, ValueError):
            return decision(False, Reason.INVALID_ARGUMENTS)
        for key, raw_value in args.items():
            # Lax validation coerces True to 1; a boolean where no boolean belongs is type confusion.
            if isinstance(raw_value, bool) and not isinstance(getattr(validated, key, None), bool):
                return decision(False, Reason.TYPE_CONFUSION)
        # 9. ownership of every referenced resource (default deny: no verifier means no proof)
        for arg_name, resource_type in policy.resource_args.items():
            if arg_name not in args or args[arg_name] is None:
                continue
            ids = args[arg_name] if isinstance(args[arg_name], (list, tuple)) else [args[arg_name]]
            verifier = self._verifiers.get(resource_type)
            if verifier is None or not user:
                return decision(False, Reason.OWNERSHIP_UNPROVEN)
            for rid in ids:
                if isinstance(rid, (dict, list, tuple, bool)) or rid is None:
                    return decision(False, Reason.INVALID_ARGUMENTS)
                try:
                    owned = bool(verifier(resource_type, rid, user))
                except Exception:  # noqa: BLE001 - a verifier failure is a missing proof, never an allow
                    owned = False
                if not owned:
                    return decision(False, Reason.RESOURCE_NOT_OWNED)
        # 10. goal and the injection risk of the context that led to the call
        side_effecting = policy.side_effect is not SideEffect.READ_ONLY
        user_norm, untrusted_norm = _norm(run.user_text), _norm(run.untrusted_text)
        # Re-proposing something the user already approved is not "derived from untrusted text".
        trusted_norm = _norm(run.user_text + "\n" + run.approved_text)
        if side_effecting and not user_norm:
            return decision(False, Reason.NO_USER_GOAL)
        tainted = run.quarantined_chunks > 0 or run.max_injection_risk >= _UNTRUSTED_RISK_WARN
        derived, destination = _derived_from_untrusted(
            _value_strings({k: v for k, v in args.items() if k in fields}), trusted_norm, untrusted_norm)
        if derived and destination and side_effecting:
            return decision(False, Reason.UNTRUSTED_DESTINATION, tainted)
        covered = _covers(policy.intent, user_norm)
        if side_effecting and derived and not covered:
            return decision(False, Reason.ARGUMENT_FROM_UNTRUSTED_CONTEXT, tainted)
        if derived and tainted and not side_effecting and not covered and policy.intent is None:
            # A read of a tool the user's words never asked for, fed by quarantined or high-risk text.
            return decision(False, Reason.ARGUMENT_FROM_UNTRUSTED_CONTEXT, tainted)
        if side_effecting and tainted and not covered:
            return decision(False, Reason.GOAL_DOES_NOT_COVER, tainted)
        return decision(True, Reason.ALLOWED, tainted)

    # -- audit --------------------------------------------------------------------------------------------
    def _audit(self, d: AuthorizationDecision) -> None:
        record = d.to_audit()
        try:
            (_LOG.info if d.allowed else _LOG.warning)(
                "tool_authorization allowed=%s tool=%s reason=%s run=%s step=%s", record["allowed"], record["tool"],
                record["reason"], record["run_id"], record["step"])
            if self._sink is not None:
                self._sink(record)
        except Exception:  # noqa: BLE001 - an audit sink failure must never turn a refusal into an allow
            pass


# --- run context from graph state -------------------------------------------------------------------------


def build_run_context(
    state: Mapping[str, Any],
    *,
    memory_header: str,
    result_untrusted_tools: frozenset[str],
    calls_in_step: int = 0,
    now: float | None = None,
) -> RunAuthContext:
    """Derive the authorization context from the trusted run state (never from the model's call).

    ``user_text`` is the goal plus every human message that is not the loaded-memory block. ``untrusted_text``
    is the output of tools whose results carry outside text, the job description and the candidate background
    (the loaded memory block is the user's own approved data: kept apart as ``approved_text``, never as intent) (third-party or pasted content is data, not the user's instruction).
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    user_parts: list[str] = [str(state.get("goal") or "")]
    untrusted_parts: list[str] = []
    approved_parts: list[str] = []
    id_to_name: dict[str, str] = {}
    messages = list(state.get("messages") or [])
    for m in messages:
        if isinstance(m, AIMessage):
            for call in getattr(m, "tool_calls", None) or []:
                id_to_name[str(call.get("id", ""))] = str(call.get("name", ""))
    for m in messages:
        content = m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)
        if isinstance(m, HumanMessage):
            (approved_parts if content.startswith(memory_header) else user_parts).append(content)
        elif isinstance(m, ToolMessage) and id_to_name.get(str(m.tool_call_id)) in result_untrusted_tools:
            untrusted_parts.append(content)
    for key in ("job_description", "candidate_background"):
        if state.get(key):
            untrusted_parts.append(str(state[key]))
    # The role the user typed (or confirmed through the human step) is the user's own input.
    user_parts += [str(state.get(k)) for k in ("target_role", "confirmed_target_role") if state.get(k)]
    taint = state.get("untrusted_context") or {}
    deadline = state.get("deadline_epoch")
    import time as _time

    current = _time.time() if now is None else now
    return RunAuthContext(
        run_id=state.get("run_id"),
        user_id=state.get("user_id"),
        step=int(state.get("step_count", 0) or 0),
        user_text="\n".join(p for p in user_parts if p),
        untrusted_text="\n".join(untrusted_parts),
        approved_text="\n".join(approved_parts),
        calls_made=len(state.get("tool_history") or []),
        calls_in_step=calls_in_step,
        seen_fingerprints=tuple(state.get("tool_call_fps") or ()),
        max_injection_risk=float(taint.get("max_injection_risk", 0.0) or 0.0),
        quarantined_chunks=int(taint.get("quarantined_chunks", 0) or 0),
        disabled_tools=frozenset(state.get("disabled_tools") or ()),
        cancelled=bool(state.get("cancelled")),
        control_required=bool(state.get("control_required")),
        expired=bool(deadline is not None and float(deadline) <= current),
    )


def bounded_append(items: list, value: Any, limit: int) -> list:
    out = list(items or [])
    out.append(value)
    return out[-limit:]
