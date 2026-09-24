"""Shared helpers for identity/platform tests (Capstone P1/E1).

Builds a FastAPI app wired to a REAL, isolated SQLite database (so the whole auth
stack — accounts, sessions, tokens, entitlements, audit — exercises real SQL) with
an in-memory email capture. No provider/network call is ever made.
"""

from __future__ import annotations

import os
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api import dependencies as deps
from src.api.config import ApiSettings
from src.api.main import create_app
from src.auth_repository import AccountRepository
from src.mail import MemoryEmailSender
from src.persistence import Base, make_session_factory
from src.repository import InterviewRepository

SESSION_COOKIE = "ask4mo_session"


def build_auth_app(env: str = "test"):
    """Return (app, repo, mail) with a fresh temp SQLite DB and captured email."""
    os.environ.setdefault("EMAIL_PROVIDER", "memory")
    db_path = os.path.join(tempfile.mkdtemp(prefix="ask4mo_auth_"), "auth.db")
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True
    )
    Base.metadata.create_all(engine)
    repo = InterviewRepository(make_session_factory(engine))
    mail = MemoryEmailSender()

    app = create_app(ApiSettings(env=env, frontend_origins=("http://localhost:3000",)))
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_email_sender] = lambda: mail
    return app, repo, mail


def account_repo(repo: InterviewRepository) -> AccountRepository:
    return AccountRepository(repo.session_factory)


def register(client: TestClient, email: str, password: str, display_name: str | None = None):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )


def login_token(client: TestClient, email: str, password: str) -> str | None:
    """Log in and return the RAW session token from Set-Cookie (works in prod env too).

    TestClient will not store a Secure cookie over http, so tests pass the token back
    explicitly via ``cookies={SESSION_COOKIE: token}``.
    """
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None
    set_cookie = r.headers.get("set-cookie", "")
    if f"{SESSION_COOKIE}=" not in set_cookie:
        return None
    return set_cookie.split(f"{SESSION_COOKIE}=")[1].split(";")[0]


def cookies_for(token: str) -> dict[str, str]:
    return {SESSION_COOKIE: token}


def verification_token(mail: MemoryEmailSender) -> str | None:
    for msg in reversed(mail.sent):
        if msg.category == "email_verification" and "token=" in msg.body:
            return msg.body.split("token=")[1].split()[0]
    return None


def reset_token(mail: MemoryEmailSender) -> str | None:
    for msg in reversed(mail.sent):
        if msg.category == "password_reset" and "token=" in msg.body:
            return msg.body.split("token=")[1].split()[0]
    return None
