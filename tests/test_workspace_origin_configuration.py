"""Isolate the shared invitation-origin and hosted startup contracts."""
import os
from unittest.mock import patch

import pytest

from src.api.env_validation import validate_runtime_config
from src.api.main import create_app
from src.application.auth_service import AuthConfig


# Validation-only configuration: no connections or provider calls are made.
PRODUCTION_ENV = {
    "API_ENV": "production",
    "FRONTEND_ORIGINS": "https://frontend.example.test",
    "DATABASE_URL": "postgresql://synthetic:synthetic@localhost/synthetic",
    "APP_BASE_URL": "https://app.example.test",
    "PAUSED_CAPABILITIES": "public_registration",
    "RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED": "true",
}
MISSING_ORIGIN = "APP_BASE_URL must be set (used for links, cookies, OIDC redirect)."
HTTPS_ORIGIN = "APP_BASE_URL must be an https:// origin in production (verification and recovery links use it)."


@pytest.mark.parametrize("value", [None, "", "   "], ids=["missing", "empty", "whitespace"])
def test_production_startup_refuses_only_missing_application_origin(value):
    env = dict(PRODUCTION_ENV)
    if value is None:
        del env["APP_BASE_URL"]
    else:
        env["APP_BASE_URL"] = value
    with patch.dict(os.environ, env, clear=True):
        assert validate_runtime_config("production").critical == [MISSING_ORIGIN]
        with pytest.raises(RuntimeError, match="APP_BASE_URL must be set") as exc:
            create_app()
        assert MISSING_ORIGIN in str(exc.value)


def test_production_startup_refuses_only_non_https_application_origin():
    with patch.dict(os.environ, {**PRODUCTION_ENV, "APP_BASE_URL": "http://app.example.test"}, clear=True):
        assert validate_runtime_config("production").critical == [HTTPS_ORIGIN]
        with pytest.raises(RuntimeError, match="APP_BASE_URL must be an https:// origin") as exc:
            create_app()
        assert HTTPS_ORIGIN in str(exc.value)


def test_production_startup_accepts_synthetic_https_application_origin():
    with patch.dict(os.environ, PRODUCTION_ENV, clear=True):
        assert validate_runtime_config("production").critical == []
        app = create_app()
        assert app.state.env_report.ok


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"APP_BASE_URL": "  https://app.example.test///  ", "FRONTEND_ORIGINS": "https://other.example.test"},
         "https://app.example.test"),
        ({"APP_BASE_URL": "  ", "FRONTEND_ORIGINS": " https://first.example.test/ , https://second.example.test "},
         "https://first.example.test"),
        ({}, "http://localhost:3000"),
    ],
    ids=["app-base-precedence-and-normalization", "first-frontend-origin-fallback", "development-default"],
)
def test_shared_auth_origin_resolution_precedence_and_normalization(env, expected):
    with patch.dict(os.environ, env, clear=True):
        assert AuthConfig.from_env().app_base_url == expected
