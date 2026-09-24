"""Database models and engine/session wiring (SQLAlchemy 2.0).

A single mature ORM backs both local development (SQLite) and production
(PostgreSQL) via one ``DATABASE_URL``. The UI never touches these models
directly — all access goes through :mod:`src.repository`, which enforces
per-user isolation.

Only appropriate information is stored (see the Phase 21 spec): user identity,
interview configuration/questions/answers/evaluations, delivery metrics,
**aggregated** visual metrics, the final report and usage/cost. Never stored:
camera video, face frames, biometric templates, permanent API keys, or raw
audio.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

__all__ = [
    "Base",
    "User",
    "Interview",
    "Question",
    "Answer",
    "Report",
    "PreparationMemory",
    "UserFeedback",
    "InterviewSession",
    "AccountIdentity",
    "PasswordCredential",
    "AuthSession",
    "AuthToken",
    "ProductEntitlement",
    "AuditEvent",
    "UserPreference",
    "make_engine",
    "make_session_factory",
    "init_db",
    "utcnow",
]

# --- identity/platform vocabulary (Capstone P1/E1) ---------------------------
# Platform role is the ONLY overloaded-free "role" the principal carries. It is
# deliberately separate from a workspace role (membership-scoped, deferred to the
# Teams phase) and from a product entitlement (tier, see ProductEntitlement).
PLATFORM_ROLE_USER = "user"
PLATFORM_ROLE_ADMIN = "platform_admin"
PLATFORM_ROLES = (PLATFORM_ROLE_USER, PLATFORM_ROLE_ADMIN)

# Account lifecycle status (privacy/account foundation).
ACCOUNT_STATUS_ACTIVE = "active"
ACCOUNT_STATUS_DEACTIVATED = "deactivated"
ACCOUNT_STATUS_DELETION_REQUESTED = "deletion_requested"

# Product tiers (entitlement FOUNDATION only — no billing in P1).
TIER_BASIC = "basic"
TIER_PREMIUM = "premium"
PRODUCT_TIERS = (TIER_BASIC, TIER_PREMIUM)

# Auth token purposes.
TOKEN_PURPOSE_EMAIL_VERIFICATION = "email_verification"
TOKEN_PURPOSE_PASSWORD_RESET = "password_reset"

# Response presentation depth (Capstone P2/E2). This is a PRESENTATION preference —
# distinct from the model/capability profile (fast/balanced/advanced) and from any
# future personality/tone preference. It never changes what the agent computes; it
# only controls how much of the (full) grounded answer is shown before "Show more".
RESPONSE_DETAIL_BRIEF = "brief"
RESPONSE_DETAIL_DETAILED = "detailed"
RESPONSE_DETAIL_VALUES = (RESPONSE_DETAIL_BRIEF, RESPONSE_DETAIL_DETAILED)

# Internationalization (Capstone P3.5). Two INDEPENDENT language preferences, both
# distinct from each other, from the model profile, and from the P3 dictation locale:
#   * interface_locale     — the UI language (application locale).
#   * conversation_language — the language the candidate wants Mo to communicate in.
# Bounded to the supported Ask4Mo candidate-product language set. A language is NOT a
# labour market: it never changes retrieval/salary/credential geography.
SUPPORTED_LOCALES = ("en", "de", "fr", "es", "it", "pt", "nl")
DEFAULT_LOCALE = "en"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    # An OIDC subject is only unique within its provider, so scope by both.
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_provider_subject"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # --- identity/platform foundation (Capstone P1/E1, migration 0007) --------
    # The principal's PLATFORM role (user/platform_admin) — never a workspace role
    # or a product tier. No user may self-promote (server-side enforced).
    platform_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PLATFORM_ROLE_USER, server_default=PLATFORM_ROLE_USER
    )
    # Account lifecycle (active / deactivated / deletion_requested).
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ACCOUNT_STATUS_ACTIVE, server_default=ACCOUNT_STATUS_ACTIVE
    )
    # Whether the primary email has been verified (gates flows that require it).
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memories: Mapped[list["PreparationMemory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["UserFeedback"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    identities: Mapped[list["AccountIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    credential: Mapped["PasswordCredential | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    entitlement: Mapped["ProductEntitlement | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    auth_tokens: Mapped[list["AuthToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class AccountIdentity(Base):
    """A single authentication method linked to a principal (Capstone P1/E1).

    Separates IDENTITY (a login method — email/password or a social provider) from
    the OWNER principal (:class:`User`). One user may hold several identities (e.g.
    a password identity and a linked Google identity), which is how account-linking
    and duplicate-email handling are expressed without splitting a user's data
    across rows. ``(provider, provider_subject)`` is globally unique.

    Legacy transitional identities (``provider``/``subject`` on ``users``) are
    backfilled here by migration 0007 so existing lookups keep resolving to the
    same owner and no candidate data is orphaned.
    """

    __tablename__ = "account_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_identity_provider_subject"),
        Index("ix_account_identities_email", "email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # e.g. "password", "google", or a legacy provider ("dev", an OIDC issuer).
    provider: Mapped[str] = mapped_column(String(64))
    # The stable subject within the provider (email for password; ``sub`` for OIDC).
    provider_subject: Mapped[str] = mapped_column(String(320))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="identities")


class PasswordCredential(Base):
    """A user's password hash (Capstone P1/E1) — never the password itself.

    Kept in its own table (one row per user) so the hash is not loaded on every
    user fetch and AUTHENTICATION stays cleanly separated from the principal.
    """

    __tablename__ = "password_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    # bcrypt self-describing hash string (algorithm/cost/salt embedded). Never plaintext.
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="credential")


class AuthSession(Base):
    """A server-side authentication session (Capstone P1/E1).

    The client holds an opaque random session token in an HttpOnly/Secure/SameSite
    cookie; only the token's SHA-256 hash is stored here, so a database read never
    yields a live session credential. Logout and expiry are enforced server-side
    (``revoked_at`` / ``expires_at``); the primary key IS the token hash.
    """

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user", "user_id"),)

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Coarse, non-identifying client hint for the account's session list (bounded).
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuthToken(Base):
    """A single-use, expiring token for email verification or password reset.

    Only the SHA-256 hash of the raw token is stored; the raw token travels only in
    the emailed link. ``consumed_at`` enforces single use; ``expires_at`` enforces
    expiry. ``purpose`` distinguishes the two flows.
    """

    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index("ix_auth_tokens_user_purpose", "user_id", "purpose"),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="auth_tokens")


class ProductEntitlement(Base):
    """A user's product tier (Capstone P1/E1) — the entitlement FOUNDATION.

    One row per user; ``tier`` is resolved server-side to a capability set. This is
    deliberately separate from platform role and workspace role, and is
    future-billing-ready (a ``source`` records how the tier was granted) WITHOUT any
    billing/payment logic in P1.
    """

    __tablename__ = "product_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    tier: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TIER_BASIC, server_default=TIER_BASIC
    )
    # How the tier was granted (e.g. "default", "admin_grant"); never payment data.
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="entitlement")


class UserPreference(Base):
    """Low-sensitivity, user-scoped product preferences (Capstone P2/E2).

    Currently holds only ``response_detail`` (brief/detailed) — the presentation depth
    of Mo's answers. It is NOT candidate content, NOT a model profile, and NOT a
    personality setting; it is available to every tier (never entitlement-gated).
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    response_detail: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RESPONSE_DETAIL_BRIEF,
        server_default=RESPONSE_DETAIL_BRIEF,
    )
    # P3.5: UI language and Mo-conversation language (independent; bounded allow-list).
    interface_locale: Mapped[str] = mapped_column(
        String(8), nullable=False, default=DEFAULT_LOCALE, server_default=DEFAULT_LOCALE
    )
    conversation_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default=DEFAULT_LOCALE, server_default=DEFAULT_LOCALE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="preferences")


class AuditEvent(Base):
    """A bounded security/privacy audit event (Capstone P1/E1).

    Answers WHO did WHAT to WHAT, WHEN and with what RESULT — without becoming a
    surveillance log. It stores NO password, token, provider secret, prompt,
    chain-of-thought, CV/interview content or other private candidate content; the
    optional ``context`` JSON is a small, safe, allow-listed projection.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor", "actor_user_id"),
        Index("ix_audit_events_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Nullable: some events (e.g. a failed login for an unknown email) have no actor.
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[str] = mapped_column(String(32), default="success")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PreparationMemory(Base):
    """Long-term, user-scoped preparation memory (Sprint 4 Phase 7).

    Selective, structured, cross-session preparation facts (recurring gaps,
    strengths, completed topics, preferences, goals, target roles). Stores only a
    concise ``summary`` — never a whole conversation, JD, CV, transcript, interview
    answer, retrieved evidence, provider response or system prompt. Distinct from
    the transient LangGraph checkpoint (short-term execution state).
    """

    __tablename__ = "preparation_memories"
    __table_args__ = (
        Index("ix_preparation_memories_user_category", "user_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(500))
    target_role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Candidate "pin": prefer this memory within otherwise-relevant memories at load
    # time (P2). Deterministic priority only — never makes memory an instruction and
    # never overrides the current request. Existing rows default to False (migration 0005).
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The agent run this memory was created from, when known (no cross-user leak:
    # ownership is always enforced via user_id, never via this field).
    source_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="memories")


class UserFeedback(Base):
    """Candidate feedback on ONE logical output (post-Sprint 4 P5).

    A user-scoped rating (helpful / not_helpful) + optional bounded comment attached by
    reference to an Agent answer, Interview evaluation or final report. Stores NO copy of
    any answer, prompt, JD, CV, evaluation, report, memory, retrieved evidence, system
    prompt, provider output or checkpoint — only references, the rating and the comment.
    """

    __tablename__ = "user_feedback"
    __table_args__ = (
        # One current rating per (user, surface, logical output) — an upsert target.
        UniqueConstraint("user_id", "surface", "target_id", name="uq_user_feedback_target"),
        Index("ix_user_feedback_surface", "surface"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    surface: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(128))
    rating: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="feedback")


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        # Crash-safe completed-history idempotency (Sprint 4 Phase 10 correction): a
        # durable interview session maps to at most ONE completed history row per user.
        # A unique INDEX (not a table constraint) so NULLs are distinct — legacy rows
        # with source_session_id = NULL never collide — and it is SQLite+Postgres
        # portable. Never keyed on candidate data.
        Index("uq_interviews_user_source_session", "user_id", "source_session_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # The durable in-progress session this completed interview was saved from, when
    # known (nullable for legacy rows and non-session saves). An idempotency/linking
    # seam only — it does NOT merge in-progress session storage with History.
    source_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="interviews")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )
    report: Mapped["Report | None"] = relationship(
        back_populates="interview", cascade="all, delete-orphan", uselist=False
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    canonical_question: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timing_guidance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_deep_dive: Mapped[bool] = mapped_column(Boolean, default=False)
    # For Deep Dive branch relationships: the position of the parent question.
    parent_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    interview: Mapped[Interview] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", uselist=False
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, default="")
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timing_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Aggregated visual metrics ONLY — never frames or biometric data.
    visual_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    question: Mapped[Question] = relationship(back_populates="answer")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="report")


class InterviewSession(Base):
    """Durable IN-PROGRESS interview session state (Sprint 4 Phase 10).

    This is operational, resumable state — the serialised ``SessionData`` for an
    interview a candidate is still taking — and is DISTINCT from the completed
    interview record in ``interviews``/``reports`` (long-term history). A candidate
    can refresh the browser or the backend can restart without losing an in-progress
    interview because the state lives here, not in process memory.

    The state machine (``SessionManager``) is unchanged; only its ``SessionData`` is
    serialised here via ``src.interview.session_codec`` (explicit JSON, never pickle).
    ``version`` provides optimistic concurrency; ``active_operation`` /
    ``operation_leased_at`` provide a bounded, recoverable lease so a paid model call
    is not launched twice concurrently. Ownership is always enforced by ``user_id``.
    """

    __tablename__ = "interview_sessions"
    __table_args__ = (
        # A given idempotency key maps to at most one session per user. NULL keys are
        # distinct (many keyless sessions per user are allowed).
        UniqueConstraint("user_id", "idempotency_key", name="uq_interview_sessions_user_idem"),
        Index("ix_interview_sessions_user_status", "user_id", "status"),
    )

    # Opaque, random, non-sequential id (set by the store; never a DB sequence).
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The serialised SessionData (safe JSON via the codec) and its schema version.
    state_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    # Optimistic concurrency control: every save requires the loaded version and
    # increments it; a stale write updates zero rows and is rejected.
    version: Mapped[int] = mapped_column(Integer, default=1)
    # A convenience projection of SessionData.state for cheap listing/filtering. Never
    # the authority for transitions — that remains SessionManager.
    status: Mapped[str] = mapped_column(String(32), default="SETUP")
    # Durable operation lease (bounded, recoverable) around provider-backed mutations.
    active_operation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operation_leased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


def make_engine(database_url: str) -> Engine:
    """Create an engine; SQLite needs cross-thread access for Streamlit."""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(database_url, future=True, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(engine: Engine, *, force: bool = False) -> None:
    """Create tables for local SQLite development/tests.

    Production databases (non-SQLite) are schema-owned by Alembic — run
    ``alembic upgrade head``. This never silently creates or alters a production
    schema via ``create_all``; pass ``force=True`` only for a deliberate,
    non-production bootstrap.
    """
    if force or engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
