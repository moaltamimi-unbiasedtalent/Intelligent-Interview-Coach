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
    "InterviewSession",
    "make_engine",
    "make_session_factory",
    "init_db",
    "utcnow",
]


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
    # The agent run this memory was created from, when known (no cross-user leak:
    # ownership is always enforced via user_id, never via this field).
    source_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="memories")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
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
