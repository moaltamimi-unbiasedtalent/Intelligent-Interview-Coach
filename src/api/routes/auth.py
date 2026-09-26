"""Authentication & account routes (Capstone P1/E1).

The trusted production identity is a server-side session carried in an HttpOnly,
SameSite cookie (never localStorage, never a body/URL). These routes own only HTTP
concerns — cookie lifecycle and status mapping — delegating every decision to the
framework-free :class:`AuthenticationService` and the authorization helpers.

No response ever echoes a password, token, hash or session id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from src.api.dependencies import (
    DEV_ENVS,
    get_account_repository,
    get_audit_repository,
    get_auth_config,
    get_auth_service,
    get_current_principal,
    get_current_user_id,
    get_document_store,
    get_oidc_provider,
    get_repository,
    get_request_id,
    get_session_repository,
    require_capability,
    require_platform_admin,
)
from src.api.schemas.auth import (
    AccountResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    PreferencesRequest,
    PremiumStatusResponse,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from src.api.rate_limit import client_ip, email_key, enforce, user_key
from src.application.authorization import Capability, capabilities_for
from src.application.auth_service import InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["auth"])

_UNIFORM_REGISTER = (
    "If that email can be registered, we've sent a verification link. "
    "Please check your inbox, then sign in."
)
_UNIFORM_FORGOT = (
    "If an account exists for that email, we've sent a password-reset link."
)


def _secure_cookies(request: Request) -> bool:
    """Cookies are Secure everywhere except the local dev/test environments."""
    env = str(getattr(getattr(request.app.state, "settings", None), "env", "development")).lower()
    return env not in DEV_ENVS


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    cfg = get_auth_config(request)
    response.set_cookie(
        key=cfg.cookie_name,
        value=token,
        max_age=cfg.session_ttl_seconds,
        httponly=True,
        secure=_secure_cookies(request),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(request: Request, response: Response) -> None:
    cfg = get_auth_config(request)
    response.delete_cookie(key=cfg.cookie_name, path="/")


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED,
             summary="Register a new account (email/password) — uniform, non-enumerating")
def register(
    body: RegisterRequest,
    request: Request,
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    # Operator pause (§21): open registration can be paused without a deploy.
    from src.api.guards import ensure_not_paused

    ensure_not_paused("public_registration")
    # Abuse bound (§18): per-IP + global. No account key here — registration must not reveal
    # whether an email exists, so the limit is IP-scoped only.
    enforce("auth_register_ip", client_ip(request))
    enforce("auth_global", "all")
    # Uniform outcome whether or not the email already exists; a verification email is
    # sent on creation. Registration does not auto-sign-in (verify then sign in).
    service.register(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        request_id=request_id,
    )
    return MessageResponse(message=_UNIFORM_REGISTER)


@router.post("/login", response_model=MessageResponse,
             summary="Sign in and open a server-side session")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    # Abuse bound (§18): per-IP, per-account (hashed email — identical whether or not the
    # account exists, so limits never leak existence), and a global ceiling.
    enforce("auth_login_ip", client_ip(request))
    enforce("auth_login_account", email_key(body.email))
    enforce("auth_global", "all")
    ua = request.headers.get("user-agent")
    try:
        result = service.login(
            email=body.email, password=body.password, user_agent=ua, request_id=request_id
        )
    except InvalidCredentialsError:
        # Generic failure (no enumeration): wrong password, unknown email or disabled.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    _set_session_cookie(request, response, result.session_token)
    return MessageResponse(message="Signed in.")


@router.post("/logout", response_model=MessageResponse,
             summary="Sign out and invalidate the current session")
def logout(
    request: Request,
    response: Response,
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    cfg = get_auth_config(request)
    token = request.cookies.get(cfg.cookie_name)
    if token:
        service.logout(session_token=token, request_id=request_id)
    _clear_session_cookie(request, response)
    return MessageResponse(message="Signed out.")


@router.post("/verify-email", response_model=MessageResponse,
             summary="Verify an email address with a single-use token")
def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    # Token-validation abuse bound (§18): per-IP. Tokens are 256-bit single-use, but this
    # bounds brute-force attempts regardless.
    enforce("auth_reset_ip", client_ip(request))
    ok = service.verify_email(token=body.token, request_id=request_id)
    if not ok:
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    return MessageResponse(message="Your email is verified.")


@router.post("/forgot-password", response_model=MessageResponse,
             summary="Request a password-reset link — uniform, non-enumerating")
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    # Abuse bound (§18): per-IP + per-account (hashed email, existence-agnostic). The response
    # stays uniform regardless of the limit, so no enumeration signal is added.
    enforce("auth_forgot_ip", client_ip(request))
    enforce("auth_forgot_account", email_key(body.email))
    service.request_password_reset(email=body.email, request_id=request_id)
    return MessageResponse(message=_UNIFORM_FORGOT)


@router.post("/reset-password", response_model=MessageResponse,
             summary="Set a new password with a single-use reset token")
def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    response: Response,
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    enforce("auth_reset_ip", client_ip(request))
    ok = service.reset_password(
        token=body.token, new_password=body.password, request_id=request_id
    )
    if not ok:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    # Reset revokes all sessions; clear any cookie on this device too.
    _clear_session_cookie(request, response)
    return MessageResponse(message="Your password has been reset. Please sign in.")


def _account_response(principal) -> AccountResponse:
    return AccountResponse(
        user_id=principal.user_id,
        email=principal.email,
        display_name=None,
        platform_role=principal.platform_role,
        tier=principal.tier,
        status=principal.status,
        email_verified=principal.email_verified,
        providers=[],
        auth_method=principal.auth_method,
        capabilities=sorted(capabilities_for(principal.tier)),
        response_detail=principal.response_detail,
        interface_locale=principal.interface_locale,
        conversation_language=principal.conversation_language,
    )


@router.get("/me", response_model=AccountResponse,
            summary="The caller's own account/profile summary")
def me(principal=Depends(get_current_principal)) -> AccountResponse:
    return _account_response(principal)


@router.patch("/preferences", response_model=AccountResponse,
              summary="Update low-sensitivity preferences (response detail, languages)")
def update_preferences(
    body: PreferencesRequest,
    account_repo=Depends(get_account_repository),
    audit=Depends(get_audit_repository),
    principal=Depends(get_current_principal),
    request_id: str = Depends(get_request_id),
) -> AccountResponse:
    # These are presentation/language preferences available to EVERY tier — never
    # entitlement-gated, never candidate content. Stored server-side, user-scoped.
    # Interface locale, conversation language and (P3) dictation locale are independent:
    # a language choice never changes labour-market geography.
    changed: dict[str, str] = {}
    if body.response_detail is not None:
        account_repo.set_response_detail(principal.user_id, body.response_detail)
        changed["response_detail"] = body.response_detail
    if body.interface_locale is not None:
        account_repo.set_interface_locale(principal.user_id, body.interface_locale)
        changed["interface_locale"] = body.interface_locale
    if body.conversation_language is not None:
        account_repo.set_conversation_language(principal.user_id, body.conversation_language)
        changed["conversation_language"] = body.conversation_language
    if changed:
        audit.record(
            event_type="account.preferences_change",
            result="success",
            actor_user_id=principal.user_id,
            request_id=request_id,
            context=changed,
        )
    # Reflect the new values without a second round-trip.
    updated = principal.__class__(
        user_id=principal.user_id,
        platform_role=principal.platform_role,
        tier=principal.tier,
        status=principal.status,
        email=principal.email,
        email_verified=principal.email_verified,
        auth_method=principal.auth_method,
        response_detail=changed.get("response_detail", principal.response_detail),
        interface_locale=changed.get("interface_locale", principal.interface_locale),
        conversation_language=changed.get("conversation_language", principal.conversation_language),
    )
    return _account_response(updated)


@router.post("/verify-email/resend", response_model=MessageResponse,
             summary="Resend the caller's email-verification link")
def resend_verification(
    service=Depends(get_auth_service),
    user_id: int = Depends(get_current_user_id),
) -> MessageResponse:
    # Mail-bomb bound (§18): per-account (the authenticated caller).
    enforce("auth_verify_resend", user_key(user_id))
    service.send_verification(user_id=user_id)
    return MessageResponse(message="If your email is unverified, we've sent a new link.")


# --- entitlement enforcement demonstration (server-side, non-destructive) -----


@router.get("/premium/status", response_model=PremiumStatusResponse,
            summary="Premium-only endpoint demonstrating server-side entitlement enforcement")
def premium_status(
    principal=Depends(require_capability(Capability.PREMIUM_PREVIEW)),
) -> PremiumStatusResponse:
    # Reaching here means the caller's entitlement grants PREMIUM_PREVIEW. A basic-tier
    # caller is rejected with 403 by the dependency BEFORE this body runs (server-side).
    return PremiumStatusResponse(
        entitled=True,
        tier=principal.tier,
        message="Premium features are available on your plan.",
    )


# --- social login (Google OIDC — bounded; live UNVALIDATED) -------------------

_OIDC_STATE_COOKIE = "ask4mo_oidc_state"
_OIDC_NEXT_COOKIE = "ask4mo_oidc_next"


def _oidc_redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/v1/auth/oidc/google/callback"


@router.get("/oidc/google/start",
            summary="Begin Google sign-in (returns the authorization URL; sets CSRF state)")
def google_start(
    request: Request,
    response: Response,
    next: str = Query(default="/", max_length=512),
    provider=Depends(get_oidc_provider),
) -> dict:
    from src.authsec import tokens
    from src.application.oidc import is_safe_redirect

    enforce("auth_oidc_start_ip", client_ip(request))
    if provider is None:
        raise HTTPException(status_code=404, detail="Google sign-in is not available.")
    state = tokens.generate_token(16)
    safe_next = next if is_safe_redirect(next) else "/"
    secure = _secure_cookies(request)
    # Short-lived, HttpOnly CSRF state + post-login destination.
    response.set_cookie(_OIDC_STATE_COOKIE, state, max_age=600, httponly=True,
                        secure=secure, samesite="lax", path="/")
    response.set_cookie(_OIDC_NEXT_COOKIE, safe_next, max_age=600, httponly=True,
                        secure=secure, samesite="lax", path="/")
    return {"authorization_url": provider.authorization_url(
        state=state, redirect_uri=_oidc_redirect_uri(request))}


@router.get("/oidc/google/callback",
            summary="Complete Google sign-in (validates state, links/creates the account)")
def google_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    provider=Depends(get_oidc_provider),
    service=Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
) -> Response:
    from src.authsec import tokens
    from src.application.oidc import OidcError, is_safe_redirect

    if provider is None:
        raise HTTPException(status_code=404, detail="Google sign-in is not available.")
    cookie_state = request.cookies.get(_OIDC_STATE_COOKIE)
    # CSRF: the state echoed by the provider must match the one we issued.
    if not cookie_state or not state or not tokens.tokens_equal(cookie_state, state):
        raise HTTPException(status_code=400, detail="Sign-in could not be verified. Please try again.")
    if not code:
        raise HTTPException(status_code=400, detail="Sign-in was cancelled or failed.")
    try:
        identity = provider.exchange(code=code, redirect_uri=_oidc_redirect_uri(request))
    except OidcError:
        raise HTTPException(status_code=400, detail="Google sign-in failed. Please try again.")

    result = service.oidc_login(
        identity=identity, user_agent=request.headers.get("user-agent"), request_id=request_id
    )
    raw_next = request.cookies.get(_OIDC_NEXT_COOKIE) or "/"
    safe_next = raw_next if is_safe_redirect(raw_next) else "/"

    redirect = RedirectResponse(url=safe_next, status_code=303)
    _set_session_cookie(request, redirect, result.session_token)
    redirect.delete_cookie(_OIDC_STATE_COOKIE, path="/")
    redirect.delete_cookie(_OIDC_NEXT_COOKIE, path="/")
    return redirect


# --- privacy / account lifecycle foundation ----------------------------------


@router.get("/account/export",
            summary="Export the caller's own account data (bounded, owner-scoped)")
def export_account(
    user_id: int = Depends(get_current_user_id),
    repo=Depends(get_repository),
    account_repo=Depends(get_account_repository),
) -> dict:
    account = account_repo.get_account(user_id)
    data = repo.export_user_data(user_id)
    return {
        "account": {
            "user_id": user_id,
            "email": account.email if account else None,
            "tier": account.tier if account else None,
            "status": account.status if account else None,
            "email_verified": account.email_verified if account else False,
        },
        "data": data,
    }


@router.post("/account/delete-request", response_model=MessageResponse,
             summary="Request account deletion (foundation — flips status + audits)")
def request_account_deletion(
    request: Request,
    response: Response,
    account_repo=Depends(get_account_repository),
    audit=Depends(get_audit_repository),
    session_repo=Depends(get_session_repository),
    user_id: int = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
) -> MessageResponse:
    from src.persistence import ACCOUNT_STATUS_DELETION_REQUESTED

    account_repo.set_status(user_id, ACCOUNT_STATUS_DELETION_REQUESTED)
    session_repo.revoke_all_for_user(user_id)
    audit.record(
        event_type="account.delete_request",
        result="success",
        actor_user_id=user_id,
        request_id=request_id,
    )
    _clear_session_cookie(request, response)
    # NOTE: full hard-delete cascade (incl. agent checkpoints) is a later phase; this
    # is the deletion-request boundary (see docs/capstone/p1_e1_identity_platform.md).
    return MessageResponse(
        message="Your account is scheduled for deletion and you've been signed out."
    )


@router.post("/account/delete", response_model=MessageResponse,
             summary="Permanently delete the account and all application-controlled data")
def delete_account(
    request: Request,
    response: Response,
    repo=Depends(get_repository),
    document_store=Depends(get_document_store),
    audit=Depends(get_audit_repository),
    user_id: int = Depends(get_current_user_id),
) -> MessageResponse:
    """Complete, application-controlled account deletion (Capstone P8, §14/§15).

    Authenticated + owner-scoped (a caller can only delete their OWN account) + idempotent.
    Removes/anonymizes every app-controlled resource (DB rows, private files, agent
    checkpoints), then clears the session. Historical hosting backups follow the provider's
    retention (documented) and are not claimed as instantly erased.
    """
    from src.application.account_deletion_service import AccountDeletionService

    # Agent service (for checkpoint purge) is best-effort — never block deletion if it can't
    # be constructed in a given environment.
    agent_service = None
    try:
        from src.api.dependencies import get_agent_service

        agent_service = get_agent_service(request)
    except Exception:  # noqa: BLE001
        agent_service = None

    service = AccountDeletionService(
        repo.session_factory, document_store=document_store,
        agent_service=agent_service, audit_repository=audit)
    service.delete_account(user_id)
    _clear_session_cookie(request, response)
    return MessageResponse(
        message="Your account and data have been deleted. You've been signed out.")


# --- platform-admin foundation (guarded API only — no Admin Console UI) --------


@router.get("/admin/audit",
            summary="Recent audit events (PLATFORM_ADMIN only) — role-enforcement demo")
def admin_audit(
    principal=Depends(require_platform_admin),
    audit=Depends(get_audit_repository),
) -> dict:
    # Reaching here proves the platform-admin role server-side. This is a bounded read
    # for the foundation, NOT the Admin Console (deferred). It is not a data superuser:
    # it returns only safe audit metadata, never another user's candidate content.
    return {"events": audit.recent_for_actor(principal.user_id, limit=50)}
