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
    BigInteger,
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
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
    "Opportunity",
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
    "CandidateDocument",
    "DocumentVersion",
    "DocumentClaim",
    "CandidateStory",
    "StoryEvidence",
    "Workspace",
    "WorkspaceMembership",
    "WorkspaceInvitation",
    "ShareGrant",
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
# W10.1: code-defined admin role presets (AD-08). The column is a plain String(32) with no DB CHECK, so
# widening the vocabulary needs no migration; the permission mapping lives in
# src/application/admin_permissions.py (a test keeps the two lists identical).
PLATFORM_ROLES = (
    PLATFORM_ROLE_USER, PLATFORM_ROLE_ADMIN, "support_operator", "billing_admin",
    "knowledge_admin", "security_privacy_admin", "operations_admin",
)

# Account lifecycle status (privacy/account foundation).
ACCOUNT_STATUS_ACTIVE = "active"
ACCOUNT_STATUS_DEACTIVATED = "deactivated"
ACCOUNT_STATUS_DELETION_REQUESTED = "deletion_requested"
ACCOUNT_STATUSES = (ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_DEACTIVATED, ACCOUNT_STATUS_DELETION_REQUESTED)

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
# P10B-W9.6: single canonical source (src/locales.py); re-exported here for existing callers.
from src.locales import SUPPORTED_LOCALE_CODES as SUPPORTED_LOCALES  # noqa: F401,E402  (re-export)
DEFAULT_LOCALE = "en"

# Coaching style (Capstone P10B Wave 2) — bounded tone preference for ONE Mo (not personas).
# The enum + trusted directive live in `src/coaching_style.py`; the model default comes from there.
from src.coaching_style import DEFAULT_COACHING_STYLE  # noqa: E402,F401 (used in the column default)

# Account-default CAREER GEOGRAPHY (Capstone P10B Wave 2). A bounded, validated set of career
# markets. It is DELIBERATELY independent of interface/conversation/dictation language and is NEVER
# inferred from a locale (a German UI does not imply the German market). "" means unspecified.
CAREER_GEOGRAPHIES = (
    "", "global", "de", "at", "ch", "fr", "es", "it", "pt", "nl", "be", "lu",
    "gb", "ie", "us", "ca", "au", "nz", "other",
)
DEFAULT_CAREER_GEOGRAPHY = ""

# --- Private candidate documents & evidence (Capstone P4/E2/E3) ---------------
# Bounded document categories (never silently inferred).
DOC_CATEGORY_CV = "cv"
DOC_CATEGORY_JOB_DESCRIPTION = "job_description"
DOC_CATEGORY_PORTFOLIO = "portfolio"
DOC_CATEGORY_BRIEF = "company_brief"
DOC_CATEGORY_OTHER = "other"
DOC_CATEGORIES = (
    DOC_CATEGORY_CV, DOC_CATEGORY_JOB_DESCRIPTION, DOC_CATEGORY_PORTFOLIO,
    DOC_CATEGORY_BRIEF, DOC_CATEGORY_OTHER,
)
# Explicit document lifecycle statuses.
DOC_STATUS_UPLOADED = "uploaded"
DOC_STATUS_PROCESSING = "processing"
DOC_STATUS_REVIEW_REQUIRED = "review_required"
DOC_STATUS_READY = "ready"
DOC_STATUS_FAILED = "failed"
DOC_STATUS_DELETED = "deleted"
# Extraction origin (native parser vs OCR) — carried for provenance/labelling.
EXTRACTION_ORIGIN_NATIVE = "native"
EXTRACTION_ORIGIN_OCR = "ocr"
# Failure taxonomy (P10B Wave 3) — a bounded, machine-readable reason a version FAILED, so the
# UI can show a localized, actionable message instead of a single generic "couldn't read the
# file". None of these carry internal exception text, paths, providers or secrets.
DOC_FAIL_ENCRYPTED = "encrypted"          # password-protected document
DOC_FAIL_CORRUPT = "corrupt"              # unreadable/damaged file
DOC_FAIL_OCR_UNAVAILABLE = "ocr_unavailable"  # scanned/image doc but OCR not enabled here
DOC_FAIL_OCR_FAILED = "ocr_failed"        # OCR engine ran but could not read the scan
DOC_FAIL_NO_TEXT = "no_text"             # parsed/OCR'd but contained no readable text
DOC_FAIL_INTERNAL = "internal"           # unexpected processing error (details never leaked)
DOC_FAIL_KINDS = (
    DOC_FAIL_ENCRYPTED, DOC_FAIL_CORRUPT, DOC_FAIL_OCR_UNAVAILABLE,
    DOC_FAIL_OCR_FAILED, DOC_FAIL_NO_TEXT, DOC_FAIL_INTERNAL,
)
# Claim review states (candidate-controlled).
CLAIM_PENDING = "pending"
CLAIM_ACCEPTED = "accepted"
CLAIM_EDITED = "edited"
CLAIM_REJECTED = "rejected"
# Story provenance/verification states (must remain distinguishable).
STORY_SOURCE_BACKED = "source_backed"
STORY_USER_CORRECTED = "user_corrected"
STORY_USER_CREATED = "user_created"
STORY_MODEL_SUGGESTED = "model_suggested"
# Whether a source-backed story still has live supporting evidence.
STORY_EVIDENCE_VERIFIED = "verified"
STORY_EVIDENCE_REVOKED = "source_revoked"
STORY_EVIDENCE_NONE = "none"

# --- Teams / Workspaces & explicit sharing (Capstone P6.5) --------------------
# Workspace role lives on the MEMBERSHIP, never on the User (orthogonal to platform
# role and to product entitlement). Bounded to two roles by design.
WORKSPACE_ROLE_OWNER = "workspace_owner"
WORKSPACE_ROLE_MEMBER = "workspace_member"
WORKSPACE_ROLES = (WORKSPACE_ROLE_OWNER, WORKSPACE_ROLE_MEMBER)
# Workspace lifecycle.
WORKSPACE_STATUS_ACTIVE = "active"
WORKSPACE_STATUS_DEACTIVATED = "deactivated"
# Membership lifecycle (a removed/left member row is kept for audit, marked inactive).
MEMBERSHIP_STATUS_ACTIVE = "active"
MEMBERSHIP_STATUS_REMOVED = "removed"
MEMBERSHIP_STATUS_LEFT = "left"
# Invitation lifecycle (single-use, opaque, expiring token stored hashed).
INVITATION_STATUS_PENDING = "pending"
INVITATION_STATUS_ACCEPTED = "accepted"
INVITATION_STATUS_DECLINED = "declined"
INVITATION_STATUS_EXPIRED = "expired"
INVITATION_STATUS_REVOKED = "revoked"
# Explicit sharing: the ALLOW-LISTED shareable resource types (never a raw document,
# CV text, Memory, auth data or audit trail). Ownership never transfers on a share.
# OPERATIONAL (durable, owner-scoped, with a wired loader): interview report + story.
SHARE_RESOURCE_REPORT = "interview_report"
SHARE_RESOURCE_STORY = "story"
# PLANNED — not yet a durable, owned resource with a stable id + owner-scoped loader, so it
# is deliberately EXCLUDED from the operational allowlist (a share attempt is rejected).
SHARE_RESOURCE_PREP_SUMMARY = "preparation_summary"
SHAREABLE_RESOURCE_TYPES = (SHARE_RESOURCE_REPORT, SHARE_RESOURCE_STORY)
SHARE_PERMISSION_VIEW = "view"          # VIEW-only in P6.5 (no edit permissions)
SHARE_STATUS_ACTIVE = "active"
SHARE_STATUS_REVOKED = "revoked"


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
    # First-run onboarding lifecycle (Capstone P10B Wave 2). NULL completed_at = onboarding not
    # yet finished (new accounts). The 0013 migration BACKFILLS every existing account to completed
    # so no current user is ever blocked. `onboarding_step` supports resuming an interrupted flow.
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    onboarding_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(
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
    # Step-up (P10B-W10.13): password re-authentication of THIS session until ``elevated_until``. Not MFA; never a browser token.
    elevated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    elevated_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    # P10B Wave 2 personalisation (all low-sensitivity, every tier, never entitlement-gated):
    #   * coaching_style   — bounded tone for Mo's coaching prose (NEVER changes scoring/rubric).
    #   * career_geography — account-default target market (independent of any language).
    #   * target_role      — account-default career-focus role (a default, not the Wave 6 Opportunity).
    coaching_style: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DEFAULT_COACHING_STYLE, server_default=DEFAULT_COACHING_STYLE
    )
    career_geography: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DEFAULT_CAREER_GEOGRAPHY, server_default=""
    )
    target_role: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="preferences")


class CandidateDocument(Base):
    """A private candidate document (Capstone P4). Owner-scoped; DATA, never a prompt.

    The logical document; each uploaded file is a :class:`DocumentVersion`. The original
    file is stored privately (never a public URL) under a random ``storage_key`` on the
    current version. Nothing here becomes public knowledge or approved memory
    automatically.
    """

    __tablename__ = "candidate_documents"
    __table_args__ = (Index("ix_candidate_documents_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32), default=DOC_CATEGORY_OTHER)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default=DOC_STATUS_UPLOADED)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship()
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version"
    )
    claims: Mapped[list["DocumentClaim"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(Base):
    """One uploaded file for a document (Capstone P4). Stable provenance target.

    Extracted claims and (later) stories reference the version that produced them, so a
    replaced CV keeps historical provenance. The private file lives at ``storage_key``
    (opaque/random); it is never a public path/URL.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_document_versions_storage_key"),
        Index("ix_document_versions_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("candidate_documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(128))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_origin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=DOC_STATUS_UPLOADED)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Bounded, machine-readable failure taxonomy (P10B Wave 3); see DOC_FAIL_* above.
    failure_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[CandidateDocument] = relationship(back_populates="versions")


class DocumentClaim(Base):
    """A structured, provenance-bearing claim extracted from a document (Capstone P4).

    Deterministic extraction only — never a fabricated/inferred fact. The candidate
    reviews each claim (accept/edit/reject) before it is reusable. ``edited_text`` marks
    a USER-CORRECTED value; the original ``text`` is preserved for provenance.
    """

    __tablename__ = "document_claims"
    __table_args__ = (Index("ix_document_claims_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("candidate_documents.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"))
    claim_type: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_state: Mapped[str] = mapped_column(String(16), default=CLAIM_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    document: Mapped[CandidateDocument] = relationship(back_populates="claims")


class CandidateStory(Base):
    """A reusable interview story/example (Capstone P4/E3). Owner-scoped, private.

    Provenance/verification state is explicit and must stay truthful: a source-backed
    story whose supporting claims are all deleted becomes ``source_revoked`` (never
    silently "verified"). Model-suggested text is labelled and editable; unsupported
    metrics are never fabricated.
    """

    __tablename__ = "candidate_stories"
    __table_args__ = (Index("ix_candidate_stories_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    competencies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=STORY_USER_CREATED)
    evidence_state: Mapped[str] = mapped_column(String(24), default=STORY_EVIDENCE_NONE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    evidence: Mapped[list["StoryEvidence"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


class StoryEvidence(Base):
    """Links a story to a supporting document claim (Capstone P4/E3).

    When the underlying claim/document is deleted this link is removed (FK cascade); the
    story service then re-derives the story's evidence_state so a source-backed story can
    never remain "verified" with no live evidence.
    """

    __tablename__ = "story_evidence"
    __table_args__ = (
        UniqueConstraint("story_id", "claim_id", name="uq_story_evidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("candidate_stories.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("document_claims.id", ondelete="CASCADE"), index=True)

    story: Mapped[CandidateStory] = relationship(back_populates="evidence")


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
    # Optional bounded issue category from the P6 feedback taxonomy (Capstone P6.5, §24).
    # Nullable so a simple thumbs rating stays effortless; validated against the taxonomy.
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="feedback")


class Workspace(Base):
    """A bounded collaboration space (Capstone P6.5). NOT a company/legal entity — the
    name is a label only. Membership grants nothing about a member's private account."""

    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_owner", "owner_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default=WORKSPACE_STATUS_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceMembership(Base):
    """Who belongs to a workspace and their WORKSPACE role (owner/member). At most one
    membership row per (workspace, user)."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
        Index("ix_workspace_memberships_user", "user_id"),
        Index("ix_workspace_memberships_workspace", "workspace_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(24), default=WORKSPACE_ROLE_MEMBER)
    status: Mapped[str] = mapped_column(String(16), default=MEMBERSHIP_STATUS_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceInvitation(Base):
    """A secure, single-use, expiring workspace invitation. The raw token is NEVER
    stored — only its hash — and no member email is enumerable through it."""

    __tablename__ = "workspace_invitations"
    __table_args__ = (
        Index("ix_workspace_invitations_workspace", "workspace_id"),
        Index("ix_workspace_invitations_token", "token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    inviter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(24), default=WORKSPACE_ROLE_MEMBER)
    status: Mapped[str] = mapped_column(String(16), default=INVITATION_STATUS_PENDING)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ShareGrant(Base):
    """An EXPLICIT, VIEW-only, revocable grant of ONE owned resource into ONE workspace.

    Ownership stays with the candidate (a share never transfers it). Only allow-listed
    resource types may be shared; access is re-checked on every read so revocation and
    source deletion take effect immediately."""

    __tablename__ = "share_grants"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "workspace_id", "resource_type", "resource_id",
            name="uq_share_grant",
        ),
        Index("ix_share_grants_workspace", "workspace_id"),
        Index("ix_share_grants_owner", "owner_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(128))
    permission: Mapped[str] = mapped_column(String(16), default=SHARE_PERMISSION_VIEW)
    status: Mapped[str] = mapped_column(String(16), default=SHARE_STATUS_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


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
    # Optional organising link to a candidate Opportunity (P10B Wave 6). SET NULL on
    # opportunity delete so completed history is never lost; NULL for standalone/legacy rows.
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
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


class Opportunity(Base):
    """A candidate's private preparation context for ONE specific job (P10B Wave 6).

    An Opportunity groups a role + company + optional JD, and is the organising home for
    Company Intelligence, Prepare, Practice, reports and progress for that job. It is a
    candidate-preparation concept, DISTINCT from a Workspace (collaboration/sharing). It is
    owner-scoped and private by default; it grants no cross-user access and never
    auto-creates a Workspace. Interviews and in-progress sessions reference it OPTIONALLY
    (nullable FK, SET NULL on delete) so deleting an Opportunity never destroys history and
    existing standalone sessions remain valid with a NULL link.
    """

    __tablename__ = "opportunities"
    __table_args__ = (
        Index("ix_opportunities_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # A human display label (e.g. "Senior PM - Acme - Berlin"); defaults from role/company.
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    target_role: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # ISO-3166 alpha-2 hint (never inferred from language); independent of career geography.
    company_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    company_domain: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Optional link to a governed JD document; SET NULL if that document is deleted so the
    # Opportunity survives without retaining inaccessible content.
    job_description_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Bounded lifecycle: active | interviewing | offer | closed | archived.
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="opportunities")


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
    # Optional organising link to a candidate Opportunity (P10B Wave 6). SET NULL on
    # opportunity delete; NULL for standalone sessions.
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
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


# --- Customer support & ticketing (P10B-W10.3, migration 0015_support_ticketing) ------------------------
# Three DISTINCT tables keep the data boundaries physical: the ticket (operational record), the
# customer-visible message thread (candidate + support), and the Admin-only internal notes. Internal notes
# have no candidate-facing code path and are never joined into a candidate response.
SUPPORT_CATEGORIES = (
    "account_login", "opportunity", "prepare", "practice_interview", "documents", "ai_response",
    "billing", "privacy", "accessibility", "technical", "data_issue", "other",
)
SUPPORT_PRIORITIES = ("low", "normal", "high", "urgent")
SUPPORT_STATUSES = ("new", "triaged", "in_progress", "waiting_for_customer", "resolved", "closed")
SUPPORT_AUTHOR_CANDIDATE = "candidate"
SUPPORT_AUTHOR_SUPPORT = "support"
SUPPORT_AUTHOR_KINDS = (SUPPORT_AUTHOR_CANDIDATE, SUPPORT_AUTHOR_SUPPORT)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class SupportTicket(Base):
    """An operational support ticket owned by one candidate. No SLA fields: no SLA policy is approved."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(_in_list("category", SUPPORT_CATEGORIES), name="ck_support_tickets_category"),
        CheckConstraint(_in_list("priority", SUPPORT_PRIORITIES), name="ck_support_tickets_priority"),
        CheckConstraint(_in_list("status", SUPPORT_STATUSES), name="ck_support_tickets_status"),
        Index("ix_support_tickets_owner_updated", "owner_user_id", "updated_at"),
        Index("ix_support_tickets_status_updated", "status", "updated_at"),
        Index("ix_support_tickets_assignee_status", "assigned_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Opaque candidate-visible reference (uuid4 hex). Authorization never relies on its secrecy.
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16), default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(24), default="new", server_default="new")
    subject: Mapped[str] = mapped_column(String(200))
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initial_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_route: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_environment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportMessage(Base):
    """A CUSTOMER-VISIBLE message in a ticket thread (candidate or support)."""

    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint(_in_list("author_kind", SUPPORT_AUTHOR_KINDS), name="ck_support_messages_author_kind"),
        Index("ix_support_messages_ticket", "ticket_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"))
    # SET NULL: a deleted support operator's replies stay in the candidate's thread.
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_kind: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupportInternalNote(Base):
    """An ADMIN-ONLY support note. Never serialised by any candidate API or export."""

    __tablename__ = "support_internal_notes"
    __table_args__ = (Index("ix_support_internal_notes_ticket", "ticket_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"))
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Plans, subscriptions and entitlements (P10B-W10.4, migration 0016_plans_entitlements) -------------
# A plan is a stable ``plan_code`` (today only the real ones: "basic", "premium") with immutable-once-active
# VERSIONS. A version carries typed entitlement values for code-defined keys. A subscription pins ONE subject
# (a user XOR a workspace) to ONE plan version: it is an access assignment, NOT a payment (no price, provider,
# invoice or payment state exists in this model; billing is W10.5).
PLAN_STATUS_DRAFT = "draft"
PLAN_STATUS_ACTIVE = "active"
PLAN_STATUS_RETIRED = "retired"
PLAN_STATUSES = (PLAN_STATUS_DRAFT, PLAN_STATUS_ACTIVE, PLAN_STATUS_RETIRED)
SUBSCRIPTION_STATUS_ACTIVE = "active"
SUBSCRIPTION_STATUS_ENDED = "ended"
SUBSCRIPTION_STATUSES = (SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_ENDED)
SUBSCRIPTION_SOURCES = ("system_default", "migration", "admin")


class PlanVersion(Base):
    """One version of a plan. Draft is editable; active is immutable and assignable; retired is immutable and
    no longer assignable (existing subscriptions stay pinned to it). Never hard-deleted while referenced."""

    __tablename__ = "plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_code", "version", name="uq_plan_versions_code_version"),
        CheckConstraint(_in_list("status", PLAN_STATUSES), name="ck_plan_versions_status"),
        Index("uq_plan_versions_one_active", "plan_code", unique=True,
              sqlite_where=text("status = 'active'"), postgresql_where=text("status = 'active'")),
        Index("uq_plan_versions_one_draft", "plan_code", unique=True,
              sqlite_where=text("status = 'draft'"), postgresql_where=text("status = 'draft'")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    display_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default=PLAN_STATUS_DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanEntitlement(Base):
    """A typed entitlement value of a plan version. ``entitlement_key`` must be in the code registry.
    enabled=False is DISABLED; enabled=True with limit_value NULL is ENABLED/UNLIMITED; enabled=True with an
    integer limit_value >= 1 is a LIMIT. 0 is never used (it would be ambiguous)."""

    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_version_id", "entitlement_key", name="uq_plan_entitlements_key"),
        CheckConstraint("limit_value IS NULL OR (limit_value >= 1 AND enabled = 1)", name="ck_plan_entitlements_limit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_version_id: Mapped[int] = mapped_column(ForeignKey("plan_versions.id", ondelete="CASCADE"))
    entitlement_key: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Subscription(Base):
    """Assignment of one plan version to exactly one subject (user XOR workspace). History is kept: a change
    ends the old row and adds a new one. Carries no payment data."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND workspace_id IS NULL) OR (user_id IS NULL AND workspace_id IS NOT NULL)",
            name="ck_subscriptions_one_subject"),
        CheckConstraint(_in_list("status", SUBSCRIPTION_STATUSES), name="ck_subscriptions_status"),
        CheckConstraint(_in_list("source", SUBSCRIPTION_SOURCES), name="ck_subscriptions_source"),
        Index("uq_subscriptions_one_active_user", "user_id", unique=True,
              sqlite_where=text("status = 'active' AND user_id IS NOT NULL"),
              postgresql_where=text("status = 'active' AND user_id IS NOT NULL")),
        Index("uq_subscriptions_one_active_workspace", "workspace_id", unique=True,
              sqlite_where=text("status = 'active' AND workspace_id IS NOT NULL"),
              postgresql_where=text("status = 'active' AND workspace_id IS NOT NULL")),
        Index("ix_subscriptions_plan_version", "plan_version_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    plan_version_id: Mapped[int] = mapped_column(ForeignKey("plan_versions.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default=SUBSCRIPTION_STATUS_ACTIVE)
    source: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- Integration state (P10B-W10.6, migration 0017_integrations) ----------------------------------------
# ONLY the safe result of an explicit manual connection test. No secret, no credential identifier, no upstream
# response, no URL. The integration code must be in the code registry (src/integrations.py); there are no
# custom integrations.
INTEGRATION_TEST_OUTCOMES = ("success", "failure")
INTEGRATION_TEST_CATEGORIES = ("ok", "unauthorized", "timeout", "unavailable", "configuration_error",
                               "rate_limited", "unknown")


class IntegrationState(Base):
    __tablename__ = "integration_states"
    __table_args__ = (
        CheckConstraint(_in_list("last_test_outcome", INTEGRATION_TEST_OUTCOMES), name="ck_integration_states_outcome"),
        CheckConstraint(_in_list("last_test_category", INTEGRATION_TEST_CATEGORIES), name="ck_integration_states_category"),
    )

    integration_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_test_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_test_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled")
JOB_PRIORITIES = ("low", "normal", "high")
JOB_ERROR_CATEGORIES = (
    "transient", "timeout", "rate_limited", "unavailable",           # retryable
    "invalid_payload", "configuration_error", "unsupported", "unknown_job_type",   # not retryable
    "lease_expired", "internal_error",
)
JOB_WORKER_STATUSES = ("running", "stopped")


class Job(Base):
    """One durable unit of background work (P10B-W10.9). The table is the queue AND the operational history.

    Never holds a secret, a header, a raw provider response, a stack trace or private candidate content: the payload
    is validated per job type and refers to durable records by id.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(_in_list("state", JOB_STATES), name="ck_jobs_state"),
        CheckConstraint(_in_list("priority", JOB_PRIORITIES), name="ck_jobs_priority"),
        CheckConstraint("attempts >= 0", name="ck_jobs_attempts_nonneg"),
        CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts_pos"),
        CheckConstraint("attempts <= max_attempts", name="ck_jobs_attempts_le_max"),
        CheckConstraint("manual_retries >= 0", name="ck_jobs_manual_retries_nonneg"),
        # A running job always has an owner and a lease; any other state holds no lease.
        CheckConstraint(
            "(state = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (state <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_jobs_lease_matches_state"),
        CheckConstraint("last_error_category IS NULL OR " + _in_list("last_error_category", JOB_ERROR_CATEGORIES),
                        name="ck_jobs_error_category"),
        # At most one ACTIVE job per (type, idempotency key); a finished job never blocks a later one.
        Index("uq_jobs_active_idempotency", "job_type", "idempotency_key", unique=True,
              sqlite_where=text("idempotency_key IS NOT NULL AND state IN ('queued', 'running')"),
              postgresql_where=text("idempotency_key IS NOT NULL AND state IN ('queued', 'running')")),
        Index("ix_jobs_claim", "state", "available_at", "priority"),
        Index("ix_jobs_lease_expiry", "state", "lease_expires_at"),
        Index("ix_jobs_type_state", "job_type", "state"),
        Index("ix_jobs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(48))
    state: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    priority: Mapped[str] = mapped_column(String(8), default="normal", server_default="normal")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    manual_retries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_owner: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_error_message_safe: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobWorker(Base):
    """Worker presence for diagnostics: an operational instance id, no hostname or address."""

    __tablename__ = "job_workers"
    __table_args__ = (CheckConstraint(_in_list("status", JOB_WORKER_STATUSES), name="ck_job_workers_status"),)

    worker_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(12), default="running", server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    jobs_succeeded: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


# --- Governed knowledge (P10B-W10.8, migration 0019_knowledge_admin) ------------------------------------------
KNOWLEDGE_STATES = ("queued", "processing", "review_required", "approved", "indexing", "indexed", "active", "rejected", "failed", "retired")
KNOWLEDGE_LICENCES = ("public_official", "explicit_permissive", "internal_owned", "permission_recorded", "unclear", "restricted")
KNOWLEDGE_SCAN_STATUSES = ("not_scanned", "scan_passed", "scan_failed", "scan_unavailable")
KNOWLEDGE_LANGUAGES = ("en", "de", "fr", "es", "it", "pt", "nl")
KNOWLEDGE_REJECTION_REASONS = ("provenance_insufficient", "licence_not_permitted", "quality_insufficient", "out_of_scope",
                               "unsafe_content", "duplicate", "other")
KNOWLEDGE_INDEX_STATES = ("built", "removed", "removal_failed")


class KnowledgeSource(Base):
    """Stable logical identity of a platform knowledge source. Platform knowledge ONLY: never candidate content."""

    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class KnowledgeSourceVersion(Base):
    """One immutable uploaded version. Governance metadata is frozen once the version is approved."""

    __tablename__ = "knowledge_source_versions"
    __table_args__ = (
        CheckConstraint(_in_list("state", KNOWLEDGE_STATES), name="ck_ksv_state"),
        CheckConstraint("authority_level IN (1, 2, 3)", name="ck_ksv_authority"),
        CheckConstraint(_in_list("language", KNOWLEDGE_LANGUAGES), name="ck_ksv_language"),
        CheckConstraint(_in_list("licence_class", KNOWLEDGE_LICENCES), name="ck_ksv_licence"),
        CheckConstraint(_in_list("scan_status", KNOWLEDGE_SCAN_STATUSES), name="ck_ksv_scan"),
        CheckConstraint("length(checksum_sha256) = 64", name="ck_ksv_checksum"),
        CheckConstraint("version >= 1", name="ck_ksv_version"),
        CheckConstraint("byte_size >= 0", name="ck_ksv_size"),
        CheckConstraint("rejection_reason IS NULL OR " + _in_list("rejection_reason", KNOWLEDGE_REJECTION_REASONS),
                        name="ck_ksv_rejection"),
        # From approval onward a version always records who approved it and when (never fabricated afterwards).
        CheckConstraint(
            "state NOT IN ('approved', 'indexing', 'indexed', 'active') "
            "OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)", name="ck_ksv_approval_evidence"),
        UniqueConstraint("source_id", "version", name="uq_ksv_source_version"),
        UniqueConstraint("source_id", "checksum_sha256", name="uq_ksv_source_checksum"),
        # At most ONE active version per source: activation is an atomic switch of this single row.
        Index("uq_ksv_one_active", "source_id", unique=True, sqlite_where=text("state = 'active'"),
              postgresql_where=text("state = 'active'")),
        Index("ix_ksv_state", "state", "updated_at"),
        Index("ix_ksv_source", "source_id", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    language: Mapped[str] = mapped_column(String(2))
    authority_level: Mapped[int] = mapped_column(Integer)
    publisher: Mapped[str] = mapped_column(String(200), default="", server_default="")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provenance_note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    licence_class: Mapped[str] = mapped_column(String(24), default="unclear", server_default="unclear")
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    media_type: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    scan_status: Mapped[str] = mapped_column(String(20), default="not_scanned", server_default="not_scanned")
    scanner_name: Mapped[str | None] = mapped_column(String(24), nullable=True)
    preview_text: Mapped[str | None] = mapped_column(String(4100), nullable=True)   # bounded; never the full document
    extracted_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_stage: Mapped[str | None] = mapped_column(String(8), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    parse_job_public_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    index_job_public_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class KnowledgeIndexRecord(Base):
    """What was written to the governed vector collection for a version (control-plane bookkeeping only)."""

    __tablename__ = "knowledge_index_records"
    __table_args__ = (CheckConstraint(_in_list("state", KNOWLEDGE_INDEX_STATES), name="ck_kir_state"),
                      CheckConstraint("chunk_count >= 0", name="ck_kir_chunks"))

    version_id: Mapped[int] = mapped_column(ForeignKey("knowledge_source_versions.id", ondelete="CASCADE"), primary_key=True)
    collection: Mapped[str] = mapped_column(String(64))
    embedder: Mapped[str] = mapped_column(String(64))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    state: Mapped[str] = mapped_column(String(16), default="built", server_default="built")
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --- Privacy and legal administration (P10B-W10.10, migration 0020_privacy_legal_admin) -------------------------
PRIVACY_REQUEST_TYPES = ("data_access", "deletion", "correction", "consent_question", "other_privacy")
PRIVACY_REQUEST_STATUSES = ("submitted", "acknowledged", "in_progress", "waiting_for_user", "completed", "closed", "rejected")
PRIVACY_RESULT_CATEGORIES = ("export_provided", "deletion_performed", "correction_made", "information_provided",
                             "no_action_required", "unable_to_verify")
PRIVACY_REQUEST_SOURCES = ("candidate_portal", "admin_recorded")
PREPARATION_RUN_STATES = ("started", "ready", "failed", "purge_failed")
PREPARATION_RUN_SOURCES = ("created", "backfill", "lazy")
LEGAL_DOCUMENT_CODES = ("terms", "privacy", "ai_transparency")
LEGAL_VERSION_STATES = ("draft", "published", "retired")
LEGAL_ACCEPTANCE_SOURCES = ("signup", "settings", "reacceptance")


class PrivacyRequest(Base):
    """A durable privacy request (SEC-W10-04). Holds NO exported data, no IP/device, no candidate dataset snapshot."""

    __tablename__ = "privacy_requests"
    __table_args__ = (
        CheckConstraint(_in_list("request_type", PRIVACY_REQUEST_TYPES), name="ck_privacy_requests_type"),
        CheckConstraint(_in_list("status", PRIVACY_REQUEST_STATUSES), name="ck_privacy_requests_status"),
        CheckConstraint(_in_list("source", PRIVACY_REQUEST_SOURCES), name="ck_privacy_requests_source"),
        CheckConstraint("result_category IS NULL OR " + _in_list("result_category", PRIVACY_RESULT_CATEGORIES),
                        name="ck_privacy_requests_result"),
        CheckConstraint("status <> 'completed' OR (result_category IS NOT NULL AND completed_at IS NOT NULL)",
                        name="ck_privacy_requests_completed_evidence"),
        Index("ix_privacy_requests_status_created", "status", "created_at"),
        Index("ix_privacy_requests_user", "user_id"),
        Index("ix_privacy_requests_assignee_status", "assigned_user_id", "status"),
        Index("ix_privacy_requests_type", "request_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Plain integer (no FK): lets a deletion request resume after the account row is gone. Cleared when the request completes.
    subject_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(20), default="submitted", server_default="submitted")
    source: Mapped[str] = mapped_column(String(20), default="candidate_portal", server_default="candidate_portal")
    request_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    result_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    related_job_public_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PreparationRun(Base):
    """Ownership/lifecycle INDEX for durable preparation runs (PRIV-W9-01). No chat content; no FK to users on purpose, so a
    failed checkpoint purge can still be retried after the account row is gone."""

    __tablename__ = "preparation_runs"
    __table_args__ = (
        CheckConstraint(_in_list("state", PREPARATION_RUN_STATES), name="ck_preparation_runs_state"),
        CheckConstraint(_in_list("source", PREPARATION_RUN_SOURCES), name="ck_preparation_runs_source"),
        CheckConstraint("coverage_version >= 1", name="ck_preparation_runs_coverage"),
        Index("ix_preparation_runs_owner_state", "owner_user_id", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="started", server_default="started")
    source: Mapped[str] = mapped_column(String(12), default="created", server_default="created")
    coverage_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LegalDocument(Base):
    __tablename__ = "legal_documents"
    __table_args__ = (CheckConstraint(_in_list("code", LEGAL_DOCUMENT_CODES), name="ck_legal_documents_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LegalDocumentVersion(Base):
    """A registered version of a legal document. The text stays in the product's own pages; this records the version, its
    reference and (for new versions) a content hash. A published version is immutable (enforced by the service)."""

    __tablename__ = "legal_document_versions"
    __table_args__ = (
        CheckConstraint(_in_list("state", LEGAL_VERSION_STATES), name="ck_ldv_state"),
        CheckConstraint("content_hash IS NULL OR length(content_hash) = 64", name="ck_ldv_hash"),
        CheckConstraint("state = 'draft' OR published_at IS NOT NULL", name="ck_ldv_published_at"),
        CheckConstraint("state <> 'published' OR is_baseline = 1 OR content_hash IS NOT NULL", name="ck_ldv_published_hash"),
        UniqueConstraint("document_id", "version", name="uq_ldv_document_version"),
        # Exactly one CURRENT (published) version per document.
        Index("uq_ldv_one_published", "document_id", unique=True, sqlite_where=text("state = 'published'"),
              postgresql_where=text("state = 'published'")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("legal_documents.id"))
    version: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft")
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    content_ref: Mapped[str] = mapped_column(String(300))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LegalAcceptance(Base):
    """A user's recorded acceptance of ONE legal document version. No IP, no device, no fingerprint. Distinct from consent."""

    __tablename__ = "legal_acceptances"
    __table_args__ = (
        CheckConstraint(_in_list("source", LEGAL_ACCEPTANCE_SOURCES), name="ck_legal_acceptances_source"),
        UniqueConstraint("user_id", "version_id", name="uq_legal_acceptance_user_version"),
        Index("ix_legal_acceptances_version", "version_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    version_id: Mapped[int] = mapped_column(ForeignKey("legal_document_versions.id"))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(16))


# --- Mock billing (P10B-W10.5, migration 0021_billing_admin) -------------------------------------------------
# MOCK BILLING: NOT LIVE. Billing rows are commercial METADATA and never an authority for product access (that stays with the W10.4
# plans/subscriptions). Money is always integer minor units + a currency code. No card, payment-instrument, bank, tax or raw provider data.
BILLING_INTERVALS = ("month", "year")
BILLING_VISIBILITIES = ("public", "private", "internal")
BILLING_TERMS_STATES = ("active", "retired")
BILLING_APPROVAL_ACTIONS = ("price_change", "refund")
BILLING_APPROVAL_STATUSES = ("pending", "approved", "rejected", "executed", "failed", "cancelled")
BILLING_PROVIDER_SUB_STATES = ("trialing", "active", "past_due", "cancelled")
BILLING_INVOICE_STATES = ("open", "paid", "past_due", "void")
BILLING_PAYMENT_STATUSES = ("pending", "succeeded", "failed")
BILLING_PAYMENT_FAILURES = ("declined", "insufficient_funds", "expired", "processing_error", "unknown")
BILLING_REFUND_STATES = ("pending", "succeeded", "failed")
BILLING_EVENT_TYPES = ("customer_created", "subscription_updated", "invoice_opened", "invoice_paid", "payment_succeeded", "payment_failed")
BILLING_EVENT_STATES = ("received", "processed", "failed")
_ACTIVE_TERMS = "state = 'active'"


class BillingCommercialTerms(Base):
    """Versioned commercial terms of a W10.4 plan version (price, currency, interval, trial, visibility). Immutable once written: a change is a
    NEW version. No row means 'commercial terms unconfigured' (never free, never zero). Entitlements are NOT duplicated here."""

    __tablename__ = "billing_commercial_terms"
    __table_args__ = (
        CheckConstraint("amount_minor >= 0 AND amount_minor <= 100000000", name="ck_bct_amount"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_bct_currency"),
        CheckConstraint(_in_list("billing_interval", BILLING_INTERVALS), name="ck_bct_interval"),
        CheckConstraint(_in_list("visibility", BILLING_VISIBILITIES), name="ck_bct_visibility"),
        CheckConstraint(_in_list("state", BILLING_TERMS_STATES), name="ck_bct_state"),
        CheckConstraint("trial_days IS NULL OR (trial_days >= 1 AND trial_days <= 365)", name="ck_bct_trial"),
        UniqueConstraint("plan_version_id", "version", name="uq_bct_plan_version_version"),
        Index("uq_bct_one_active", "plan_version_id", unique=True, sqlite_where=text(_ACTIVE_TERMS), postgresql_where=text(_ACTIVE_TERMS)),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    plan_version_id: Mapped[int] = mapped_column(ForeignKey("plan_versions.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    billing_interval: Mapped[str] = mapped_column(String(8))
    trial_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(10), default="active", server_default="active")
    approval_public_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BillingApprovalRequest(Base):
    """A bounded second-approver workflow for price changes and refunds. The approver can never be the requester."""

    __tablename__ = "billing_approval_requests"
    __table_args__ = (
        CheckConstraint(_in_list("action_type", BILLING_APPROVAL_ACTIONS), name="ck_bar_action"),
        CheckConstraint(_in_list("status", BILLING_APPROVAL_STATUSES), name="ck_bar_status"),
        CheckConstraint("decided_by_user_id IS NULL OR requested_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
                        name="ck_bar_no_self_approval"),
        Index("uq_bar_one_pending_per_target", "action_type", "target_ref", unique=True,
              sqlite_where=text("status = 'pending'"), postgresql_where=text("status = 'pending'")),
        Index("ix_bar_status_created", "status", "requested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(16))
    target_ref: Mapped[str] = mapped_column(String(64))
    proposed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_ref: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(24), nullable=True)


class BillingCustomer(Base):
    """Mirror of a provider customer reference for ONE subject (user XOR workspace). No card, address, tax id or bank data."""

    __tablename__ = "billing_customers"
    __table_args__ = (
        CheckConstraint("(user_id IS NOT NULL AND workspace_id IS NULL) OR (user_id IS NULL AND workspace_id IS NOT NULL)", name="ck_bc_one_subject"),
        CheckConstraint(_in_list("provider", ("mock",)), name="ck_bc_provider"),
        CheckConstraint(_in_list("state", ("active", "closed")), name="ck_bc_state"),
        UniqueConstraint("provider", "provider_customer_id", name="uq_bc_provider_customer"),
        Index("uq_bc_user", "provider", "user_id", unique=True, sqlite_where=text("user_id IS NOT NULL"), postgresql_where=text("user_id IS NOT NULL")),
        Index("uq_bc_workspace", "provider", "workspace_id", unique=True, sqlite_where=text("workspace_id IS NOT NULL"),
              postgresql_where=text("workspace_id IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_customer_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    state: Mapped[str] = mapped_column(String(10), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BillingProviderSubscription(Base):
    """Mirror of a provider-side subscription. INFORMATIONAL ONLY: its state never authorises, grants or revokes product access."""

    __tablename__ = "billing_provider_subscriptions"
    __table_args__ = (
        CheckConstraint(_in_list("provider_state", BILLING_PROVIDER_SUB_STATES), name="ck_bps_state"),
        UniqueConstraint("provider", "provider_subscription_id", name="uq_bps_provider_sub"),
        Index("ix_bps_customer", "customer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_subscription_id: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[int] = mapped_column(ForeignKey("billing_customers.id", ondelete="CASCADE"))
    plan_version_id: Mapped[int] = mapped_column(ForeignKey("plan_versions.id", ondelete="RESTRICT"))
    commercial_terms_id: Mapped[int | None] = mapped_column(ForeignKey("billing_commercial_terms.id", ondelete="SET NULL"), nullable=True)
    provider_state: Mapped[str] = mapped_column(String(12))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        CheckConstraint("amount_due_minor >= 0 AND amount_paid_minor >= 0 AND amount_paid_minor <= amount_due_minor", name="ck_bi_amounts"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_bi_currency"),
        CheckConstraint(_in_list("state", BILLING_INVOICE_STATES), name="ck_bi_state"),
        UniqueConstraint("provider", "provider_invoice_id", name="uq_bi_provider_invoice"),
        Index("ix_bi_state_created", "state", "created_at"),
        Index("ix_bi_customer", "customer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_invoice_id: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[int] = mapped_column(ForeignKey("billing_customers.id", ondelete="CASCADE"))
    provider_subscription_id: Mapped[int | None] = mapped_column(ForeignKey("billing_provider_subscriptions.id", ondelete="SET NULL"), nullable=True)
    amount_due_minor: Mapped[int] = mapped_column(Integer)
    amount_paid_minor: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(10), default="open", server_default="open")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BillingPayment(Base):
    __tablename__ = "billing_payments"
    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_bp_amount"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_bp_currency"),
        CheckConstraint(_in_list("status", BILLING_PAYMENT_STATUSES), name="ck_bp_status"),
        CheckConstraint("failure_category IS NULL OR " + _in_list("failure_category", BILLING_PAYMENT_FAILURES), name="ck_bp_failure"),
        UniqueConstraint("provider", "provider_payment_id", name="uq_bp_provider_payment"),
        Index("ix_bp_status_created", "status", "created_at"),
        Index("ix_bp_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_payment_id: Mapped[str] = mapped_column(String(64))
    invoice_id: Mapped[int] = mapped_column(ForeignKey("billing_invoices.id", ondelete="CASCADE"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(10))
    failure_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BillingRefund(Base):
    __tablename__ = "billing_refunds"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_br_amount"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_br_currency"),
        CheckConstraint(_in_list("state", BILLING_REFUND_STATES), name="ck_br_state"),
        UniqueConstraint("idempotency_key", name="uq_br_idempotency"),
        UniqueConstraint("provider", "provider_refund_id", name="uq_br_provider_refund"),
        Index("ix_br_payment", "payment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_refund_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("billing_payments.id", ondelete="CASCADE"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    approval_request_id: Mapped[int | None] = mapped_column(ForeignKey("billing_approval_requests.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BillingEvent(Base):
    """A NORMALISED provider event (no raw body). The unique (provider, provider_event_id) makes ingestion idempotent."""

    __tablename__ = "billing_events"
    __table_args__ = (
        CheckConstraint(_in_list("event_type", BILLING_EVENT_TYPES), name="ck_be_type"),
        CheckConstraint(_in_list("state", BILLING_EVENT_STATES), name="ck_be_state"),
        UniqueConstraint("provider", "provider_event_id", name="uq_be_provider_event"),
        Index("ix_be_state_received", "state", "received_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_event_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(24))
    normalized_json: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(10), default="received", server_default="received")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(24), nullable=True)


AI_CONFIG_STATES = ("draft", "validated", "evaluated", "evaluation_failed", "approved", "rejected", "retired")
AI_EVAL_STATUSES = ("queued", "running", "passed", "failed", "error")
AI_APPROVAL_STATUSES = ("pending", "approved", "rejected")
AI_ENVIRONMENTS = ("development", "staging", "production")
AI_ACTIVATION_KINDS = ("activate", "rollback", "revert_to_code")


class AIConfigVersion(Base):
    """A governed AI configuration (P10B-W10.7). Content is frozen (hash-pinned) once it leaves ``draft``."""

    __tablename__ = "ai_config_versions"
    __table_args__ = (
        CheckConstraint(_in_list("state", AI_CONFIG_STATES), name="ck_aicv_state"),
        CheckConstraint("length(config_hash) = 64", name="ck_aicv_hash"),
        Index("ix_aicv_state_created", "state", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(80))
    notes: Mapped[str] = mapped_column(String(300), default="")
    state: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    config_hash: Mapped[str] = mapped_column(String(64))
    catalogue_version: Mapped[str] = mapped_column(String(24))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    base_version_id: Mapped[int | None] = mapped_column(ForeignKey("ai_config_versions.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIConfigEvaluation(Base):
    """One deterministic evaluation of one exact configuration hash. Never makes a provider call (``live_calls`` is pinned to 0)."""

    __tablename__ = "ai_config_evaluations"
    __table_args__ = (
        CheckConstraint(_in_list("status", AI_EVAL_STATUSES), name="ck_aice_status"),
        CheckConstraint("live_calls = 0", name="ck_aice_no_live_calls"),
        Index("ix_aice_version", "config_version_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    config_version_id: Mapped[int] = mapped_column(ForeignKey("ai_config_versions.id", ondelete="RESTRICT"))
    config_hash: Mapped[str] = mapped_column(String(64))
    evaluator_version: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(10), default="queued", server_default="queued")
    checks_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    live_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failure_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIConfigApproval(Base):
    """Second-approver record bound to one evaluated hash. The approver can never be the requester (DB check) nor the author (service)."""

    __tablename__ = "ai_config_approvals"
    __table_args__ = (
        CheckConstraint(_in_list("status", AI_APPROVAL_STATUSES), name="ck_aica_status"),
        CheckConstraint("decided_by_user_id IS NULL OR requested_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
                        name="ck_aica_no_self_approval"),
        Index("uq_aica_one_pending", "config_version_id", unique=True,
              sqlite_where=text("status = 'pending'"), postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    config_version_id: Mapped[int] = mapped_column(ForeignKey("ai_config_versions.id", ondelete="RESTRICT"))
    config_hash: Mapped[str] = mapped_column(String(64))
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("ai_config_evaluations.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(300), default="")


class AIConfigActivation(Base):
    """Append-only activation history per environment. At most one open (not yet deactivated) row per environment."""

    __tablename__ = "ai_config_activations"
    __table_args__ = (
        CheckConstraint(_in_list("environment", AI_ENVIRONMENTS), name="ck_aicact_env"),
        CheckConstraint(_in_list("kind", AI_ACTIVATION_KINDS), name="ck_aicact_kind"),
        Index("uq_aicact_one_open", "environment", unique=True,
              sqlite_where=text("deactivated_at IS NULL"), postgresql_where=text("deactivated_at IS NULL")),
        Index("ix_aicact_env_time", "environment", "activated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    environment: Mapped[str] = mapped_column(String(12))
    config_version_id: Mapped[int | None] = mapped_column(ForeignKey("ai_config_versions.id", ondelete="RESTRICT"), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("ai_config_approvals.id", ondelete="RESTRICT"), nullable=True)
    activated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(300), default="")


PLATFORM_ENVIRONMENTS = ("development", "staging", "production")


class PlatformPauseState(Base):
    """DURABLE operator pause state (P10B-W10.11, closes SEC-W10-05). One row per (environment, pausable capability); a row is an EXPLICIT state
    (paused or resumed) and no row means "inherit the env-seeded baseline" (``PAUSED_CAPABILITIES``). ``revision`` is the optimistic-concurrency
    token. ``reason`` is INTERNAL admin metadata and is never returned to candidates."""

    __tablename__ = "platform_pause_states"
    __table_args__ = (
        UniqueConstraint("environment", "capability", name="uq_pps_env_capability"),
        CheckConstraint(_in_list("environment", PLATFORM_ENVIRONMENTS), name="ck_pps_env"),
        CheckConstraint("revision >= 0", name="ck_pps_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    environment: Mapped[str] = mapped_column(String(12))
    capability: Mapped[str] = mapped_column(String(32))
    paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reason: Mapped[str] = mapped_column(String(200), default="")


class FeatureFlagOverride(Base):
    """DURABLE override of a CODE-DEFINED feature flag (P10B-W10.11). A row with enabled true/false is an explicit override; no row, or a row with
    enabled NULL (after a reset), means INHERIT the code/environment baseline. The flag definition lives in code; this table owns only override state."""

    __tablename__ = "feature_flag_overrides"
    __table_args__ = (
        UniqueConstraint("environment", "flag_key", name="uq_ffo_env_key"),
        CheckConstraint(_in_list("environment", PLATFORM_ENVIRONMENTS), name="ck_ffo_env"),
        CheckConstraint("revision >= 0", name="ck_ffo_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    environment: Mapped[str] = mapped_column(String(12))
    flag_key: Mapped[str] = mapped_column(String(48))
    # NULL = inherit the baseline. The row is KEPT on a reset so ``revision`` stays monotonic (no stale-write ABA after a reset and re-set).
    enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reason: Mapped[str] = mapped_column(String(200), default="")


OPERATIONAL_EVENT_TYPES = ("request", "provider_call", "retrieval")
OPERATIONAL_OUTCOMES = ("success", "client_error", "server_error", "unavailable", "hit", "abstained", "error")
AI_USAGE_WORKFLOWS = ("agent", "practice")
AI_USAGE_COST_SOURCES = ("reported", "calculated", "unavailable")
AI_USAGE_COVERAGE = ("complete", "partial", "unknown")


class OperationalMetricEvent(Base):
    """A bounded, first-party OPERATIONAL fact (P10B-W10.12): a request outcome, a provider-call outcome or a retrieval outcome. It stores NO user
    identity, no path or query (``operation`` is a code-defined label), no body and no exception text. Counted only from the day it was captured."""

    __tablename__ = "operational_metric_events"
    __table_args__ = (
        CheckConstraint(_in_list("event_type", OPERATIONAL_EVENT_TYPES), name="ck_ome_type"),
        CheckConstraint(_in_list("outcome", OPERATIONAL_OUTCOMES), name="ck_ome_outcome"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_ome_duration"),
        Index("ix_ome_occurred", "occurred_at"),
        Index("ix_ome_type_time", "event_type", "occurred_at"),
        Index("ix_ome_subsystem_time", "subsystem", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(16))
    subsystem: Mapped[str] = mapped_column(String(24))
    operation: Mapped[str] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(24), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIUsageFact(Base):
    """One CANONICAL AI usage unit (P10B-W10.12): one Agent run (cumulative, upserted) or one Practice operation. No prompt, answer, query, context or
    reasoning is ever stored. Unknown tokens/cost are NULL, never 0; cost is integer micro-USD. Deleted with the account (FK CASCADE)."""

    __tablename__ = "ai_usage_facts"
    __table_args__ = (
        UniqueConstraint("usage_key", name="uq_aiuf_usage_key"),
        CheckConstraint(_in_list("workflow", AI_USAGE_WORKFLOWS), name="ck_aiuf_workflow"),
        CheckConstraint(_in_list("cost_source", AI_USAGE_COST_SOURCES), name="ck_aiuf_cost_source"),
        CheckConstraint(_in_list("token_coverage", AI_USAGE_COVERAGE), name="ck_aiuf_token_cov"),
        CheckConstraint(_in_list("cost_coverage", AI_USAGE_COVERAGE), name="ck_aiuf_cost_cov"),
        CheckConstraint("model_calls >= 0", name="ck_aiuf_calls"),
        CheckConstraint("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) "
                        "AND (total_tokens IS NULL OR total_tokens >= 0)", name="ck_aiuf_tokens"),
        CheckConstraint("total_tokens IS NULL OR input_tokens IS NULL OR output_tokens IS NULL OR total_tokens = input_tokens + output_tokens",
                        name="ck_aiuf_total"),
        CheckConstraint("cost_usd_micros IS NULL OR cost_usd_micros >= 0", name="ck_aiuf_cost"),
        CheckConstraint("cost_source <> 'unavailable' OR cost_usd_micros IS NULL", name="ck_aiuf_unavailable_is_null"),
        Index("ix_aiuf_occurred", "occurred_at"),
        Index("ix_aiuf_workflow_time", "workflow", "occurred_at"),
        Index("ix_aiuf_model", "model_id"),
        Index("ix_aiuf_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usage_key: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    workflow: Mapped[str] = mapped_column(String(12))
    operation: Mapped[str] = mapped_column(String(32))
    model_profile: Mapped[str | None] = mapped_column(String(12), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_source: Mapped[str] = mapped_column(String(12), default="unavailable", server_default="unavailable")
    token_coverage: Mapped[str] = mapped_column(String(8), default="unknown", server_default="unknown")
    cost_coverage: Mapped[str] = mapped_column(String(8), default="unknown", server_default="unknown")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
        # Bootstrap schema (no Alembic): seed the two real plan versions the migration would have seeded.
        from src.entitlements import seed_default_plans

        with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as s:
            seed_default_plans(s)
            s.commit()


# --- P10B-W10.13: append-only audit/incident history, incidents, alerts, role-change requests ---------------------------------------------

INCIDENT_SEVERITIES = ("low", "medium", "high", "critical")
INCIDENT_STATUSES = ("open", "investigating", "monitoring", "resolved", "closed")
INCIDENT_SERVICES = ("authentication", "agent", "practice", "research", "documents", "integrations", "knowledge", "jobs",
                     "billing", "privacy", "admin", "platform")
ALERT_CATEGORIES = ("auth_failure_burst", "admin_access_denied_burst", "job_failed")
ALERT_SEVERITIES = ("low", "medium", "high", "critical")
ALERT_STATES = ("active", "acknowledged", "resolved")
ROLE_REQUEST_STATUSES = ("pending", "applied", "rejected", "cancelled", "stale")


def append_only_trigger_ddl(table: str, dialect: str) -> list[str]:
    """DDL for DB-level append-only protection of ``table`` (P10B-W10.13). DELETE is rejected. UPDATE is rejected unless the ONLY change is
    ``actor_user_id`` going from a value to NULL (the FK ``ON DELETE SET NULL`` account-deletion anonymisation). Not tamper-proof against a
    database owner/superuser, who can drop the trigger; production DBA privileges remain a deployment responsibility."""
    cols = ("id", "event_type", "target_type", "target_id", "result", "request_id", "context", "created_at") if table == "audit_events" else None
    if table == "incident_events":
        cols = ("id", "incident_id", "action", "prior_status", "new_status", "request_id", "meta", "created_at")
    assert cols is not None
    msg = f"{table} is append-only"
    if dialect == "sqlite":
        same = " AND ".join(f"NEW.{c} IS OLD.{c}" for c in cols)
        return [
            f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{msg}'); END",
            f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update BEFORE UPDATE ON {table} "
            f"WHEN NOT ({same} AND NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL) BEGIN SELECT RAISE(ABORT, '{msg}'); END",
        ]
    if dialect == "postgresql":
        # JSON columns have no equality operator in PostgreSQL, so compare their text form.
        parts = []
        for c in cols:
            parts.append(f"NEW.{c}::text IS NOT DISTINCT FROM OLD.{c}::text" if c in ("context", "meta") else f"NEW.{c} IS NOT DISTINCT FROM OLD.{c}")
        same = " AND ".join(parts)
        return [
            f"CREATE OR REPLACE FUNCTION {table}_guard() RETURNS trigger AS $$ BEGIN "
            f"IF TG_OP = 'DELETE' THEN RAISE EXCEPTION '{msg}'; END IF; "
            f"IF NOT ({same} AND NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL) THEN RAISE EXCEPTION '{msg}'; END IF; "
            f"RETURN NEW; END; $$ LANGUAGE plpgsql",
            f"DROP TRIGGER IF EXISTS trg_{table}_guard ON {table}",
            f"CREATE TRIGGER trg_{table}_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_guard()",
        ]
    return []


def append_only_trigger_drop_ddl(table: str, dialect: str) -> list[str]:
    if dialect == "sqlite":
        return [f"DROP TRIGGER IF EXISTS trg_{table}_no_delete", f"DROP TRIGGER IF EXISTS trg_{table}_no_update"]
    if dialect == "postgresql":
        return [f"DROP TRIGGER IF EXISTS trg_{table}_guard ON {table}", f"DROP FUNCTION IF EXISTS {table}_guard()"]
    return []


class AdminIncident(Base):
    """An operator-authored incident (P10B-W10.13). INTERNAL operational metadata only: never populated from candidate content; no candidate list."""

    __tablename__ = "admin_incidents"
    __table_args__ = (
        CheckConstraint(_in_list("severity", INCIDENT_SEVERITIES), name="ck_incident_severity"),
        CheckConstraint(_in_list("status", INCIDENT_STATUSES), name="ck_incident_status"),
        CheckConstraint(_in_list("affected_service", INCIDENT_SERVICES), name="ck_incident_service"),
        CheckConstraint("affected_user_estimate IS NULL OR affected_user_estimate >= 0", name="ck_incident_estimate"),
        CheckConstraint("revision >= 0", name="ck_incident_revision"),
        CheckConstraint("(status IN ('resolved','closed') AND resolved_at IS NOT NULL) OR (status NOT IN ('resolved','closed') AND resolved_at IS NULL)",
                        name="ck_incident_resolved_at"),
        Index("ix_incident_status_updated", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    severity: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="open", server_default="open")
    affected_service: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_admin_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    affected_user_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    remediation: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AdminIncidentEvent(Base):
    """Append-only incident history (P10B-W10.13). One row per mutation; no free text; DB triggers reject UPDATE/DELETE (except actor anonymisation)."""

    __tablename__ = "incident_events"
    __table_args__ = (Index("ix_incident_events_incident", "incident_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("admin_incidents.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(32))
    prior_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminIncidentTicket(Base):
    """A link from an incident to a support ticket by identifier only (P10B-W10.13). No ticket content is stored or copied."""

    __tablename__ = "incident_tickets"
    __table_args__ = (UniqueConstraint("incident_id", "ticket_id", name="uq_incident_ticket"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("admin_incidents.id", ondelete="CASCADE"), index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True)
    linked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminNotification(Base):
    """A durable IN-APP Admin alert (P10B-W10.13). Code-defined category and title; no arbitrary payload; deduplicated by a stable key."""

    __tablename__ = "admin_notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_admin_notification_dedupe"),
        CheckConstraint(_in_list("category", ALERT_CATEGORIES), name="ck_notification_category"),
        CheckConstraint(_in_list("severity", ALERT_SEVERITIES), name="ck_notification_severity"),
        CheckConstraint(_in_list("state", ALERT_STATES), name="ck_notification_state"),
        CheckConstraint("revision >= 0", name="ck_notification_revision"),
        CheckConstraint("occurrence_count >= 1", name="ck_notification_occurrences"),
        CheckConstraint("last_seen_at >= first_seen_at", name="ck_notification_seen"),
        Index("ix_notification_state_seen", "state", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(12))
    dedupe_key: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(14), default="active", server_default="active")
    source_type: Mapped[str] = mapped_column(String(24))
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AdminRoleChangeRequest(Base):
    """A governed platform-role change (P10B-W10.13): requested by one Admin, applied only when a DIFFERENT authorised Admin approves. The target
    may be neither requester nor approver. The role is applied in the same transaction as the approval and its audit row."""

    __tablename__ = "admin_role_change_requests"
    __table_args__ = (
        CheckConstraint(_in_list("status", ROLE_REQUEST_STATUSES), name="ck_role_request_status"),
        CheckConstraint("revision >= 0", name="ck_role_request_revision"),
        CheckConstraint("approver_user_id IS NULL OR requester_user_id IS NULL OR approver_user_id <> requester_user_id", name="ck_role_request_distinct"),
        CheckConstraint("requester_user_id IS NULL OR requester_user_id <> target_user_id", name="ck_role_request_not_self"),
        Index("ix_role_request_status", "status", "requested_at"),
        Index("uq_role_request_one_pending", "target_user_id", unique=True, sqlite_where=text("status = 'pending'"),
              postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    before_role: Mapped[str] = mapped_column(String(32))
    requested_role: Mapped[str] = mapped_column(String(32))
    requester_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    reason: Mapped[str] = mapped_column(String(200))
    decision_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


def _install_append_only(table_obj, table_name: str) -> None:
    """Install the append-only triggers whenever the table is created through ``create_all`` (dev/test); migrations issue the same DDL."""
    from sqlalchemy import DDL, event

    for dialect in ("sqlite", "postgresql"):
        for stmt in append_only_trigger_ddl(table_name, dialect):
            event.listen(table_obj, "after_create", DDL(stmt.replace("%", "%%")).execute_if(dialect=dialect))


_install_append_only(AuditEvent.__table__, "audit_events")
_install_append_only(AdminIncidentEvent.__table__, "incident_events")
