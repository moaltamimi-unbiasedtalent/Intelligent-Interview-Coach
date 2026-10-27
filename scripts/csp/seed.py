"""One synthetic verified account via real invitation/auth services; isolated PG only."""

import json, os, re, sys

sys.path.insert(0, "/app")
from sqlalchemy.engine import make_url

u = make_url(os.environ["DATABASE_URL"])
token = os.environ["ASK4MO_CSP_DISPOSABLE"]
assert re.fullmatch(r"[a-f0-9]{16}", token)
assert u.get_backend_name() == "postgresql"
assert u.host == "db" and u.database == "p5b_csp_" + token and u.port == 5432
assert (
    u.username == "disposable" and u.password == "synthetic-test-only" and not u.query
)
assert os.environ["API_ENV"] == "staging" and os.environ["EMAIL_PROVIDER"] == "memory"
assert not any(
    os.environ.get(k)
    for k in (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "BREVO_API_KEY",
        "AI_BUDGET_CONFIG_PATH",
    )
)
assert os.getuid() == 10001
from src.persistence import make_engine, make_session_factory
from src.application.auth_service import AuthenticationService, AuthConfig
from src.auth_repository import (
    AccountRepository,
    SessionRepository,
    TokenRepository,
    AuditRepository,
)
from src.mail import MemoryEmailSender
from src.invitations import repository as IR
from src.application import admin_audit as A

sf = make_session_factory(make_engine(os.environ["DATABASE_URL"]))
accounts, mail = AccountRepository(sf), MemoryEmailSender()
svc = AuthenticationService(
    accounts=accounts,
    sessions=SessionRepository(sf),
    auth_tokens=TokenRepository(sf),
    audit=AuditRepository(sf),
    email=mail,
    config=AuthConfig.from_env(),
)
code = IR.new_code()
audit = A.build_audit(
    event_type=A.ADMIN_INVITATION_ISSUED,
    actor_user_id=None,
    request_id=None,
    target_type="invitation",
    origin="cli",
)
IR.InvitationRepository(sf).issue(
    code_hash=IR.hash_code(code),
    ttl_days=1,
    email=None,
    issued_by_user_id=None,
    audit=audit,
)
email, password = "csp-synthetic@example.invalid", "Synthetic-CSP-Only-123!"
assert svc.register(
    email=email,
    password=password,
    display_name="Synthetic CSP",
    locale="en",
    invitation_code=code,
    require_invitation=True,
).created
verification = re.search(r"token=([^\s&]+)", mail.sent[-1].body).group(1)
assert svc.verify_email(token=verification)
account = accounts.find_by_email(email)
accounts.complete_onboarding(account.user_id)
# Consumed privately by the parent runner, never printed to workflow logs/artifacts.
print(json.dumps({"email": email, "password": password}))
