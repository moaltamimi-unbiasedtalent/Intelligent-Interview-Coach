#!/usr/bin/env python3
"""Staging live-verification skeleton for identity, email and rate limiting (05D, PG-02). DRY RUN BY DEFAULT.

Every subcommand prints a JSON report of check names and PASS / FAIL / NOT_RUN. It NEVER prints a secret, token, code, PKCE verifier, ID token, email
address, link or message content. A live action (anything that contacts Google, Brevo, Redis or a webhook URL) runs ONLY with all three of:
  1. the ``--authorise-live`` flag,
  2. ``LIVE_VERIFY_AUTHORISED=I-AUTHORISE-STAGING-LIVE-CHECKS`` in the environment,
  3. ``API_ENV=staging``.
Without them the command prints what it WOULD do and exits 0 having sent nothing. Production and local environments are always refused.

Subcommands (see docs/production/identity_live_verification_05D.md for the run order):
  oidc-config   offline: Google sign-in status, redirect trust, invitation rule for this environment
  oidc-start    offline: build the real authorization URL, verify PKCE/state/redirect, save the single-use verifier to a 0600 file
  oidc-finish   LIVE: redeem the code Google returned (callback URL from the operator's browser) through the real provider; reports every check
  email-send    LIVE: ONE test message through the real Brevo adapter to --recipient (the operator's own address)
  webhook-probe LIVE: signed, forged, old, replayed and malformed events at the staging webhook URL (needs the gate open on staging)
  redis-check   LIVE: distributed-limiter semantics against REDIS_URL under a unique key prefix (deleted afterwards)

Run from the repository root with the project interpreter. This file is a skeleton only: it was exercised offline against fakes (tests/test_identity_live_check_05d.py).
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application import identity_live_check as L  # noqa: E402


def _emit(obj: dict) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def _dry(plan: str, reason: str) -> int:
    _emit({"mode": "dry_run", "would_do": plan, "refused_because": reason, "sent": False})
    return 0


def _write_private(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def cmd_oidc_config(args) -> int:
    from src.application.oidc import oidc_status
    from src.invitations.policy import invitation_required

    env = os.environ.get("API_ENV", "development")
    redirect = (os.environ.get("OIDC_REDIRECT_URI") or "").strip()
    trusted = redirect.startswith("https://") and redirect.split("?")[0].endswith("/api/v1/auth/oidc/google/callback")
    rep = L.Report("oidc_config")
    st = oidc_status()
    rep.add("google_sign_in_enabled", L.PASS if st["enabled"] else L.FAIL, st["reason"])
    rep.add("redirect_uri_trusted_https", L.PASS if trusted else L.FAIL)
    rep.add("invitation_required_in_this_environment", L.PASS if invitation_required(env) else L.FAIL, f"API_ENV={env}")
    _emit(rep.to_dict())
    return 0 if rep.passed else 1


def cmd_oidc_start(args) -> int:
    from src.application.oidc import GoogleOidcProvider, new_pkce_verifier, oidc_status, pkce_challenge
    from src.authsec import tokens
    from src.core import secrets as S

    if not oidc_status()["enabled"]:
        _emit({"error": "google sign-in is disabled or incomplete (see oidc-config)"})
        return 1
    redirect = (os.environ.get("OIDC_REDIRECT_URI") or "").strip()
    cid = S.read_setting("GOOGLE_CLIENT_ID") or ""
    provider = GoogleOidcProvider(client_id=cid, client_secret=S.read_setting("GOOGLE_CLIENT_SECRET") or "")
    verifier, state = new_pkce_verifier(), tokens.generate_token(16)
    url = provider.authorization_url(state=state, redirect_uri=redirect, code_challenge=pkce_challenge(verifier))
    rep = L.check_authorization_url(url, verifier=verifier, state=state, redirect_uri=redirect, client_id=cid)
    out = rep.to_dict()
    out["next_step"] = "open the authorization URL (written to the url file) in a browser signed in to a TEST Google account, then pass the final callback URL to oidc-finish"
    if rep.passed:
        _write_private(Path(args.state_file), json.dumps({"verifier": verifier, "state": state}))
        _write_private(Path(args.url_file), url)                      # contains client id, state and challenge only (no secret); kept private anyway
        out["state_file"], out["url_file"] = args.state_file, args.url_file
    _emit(out)
    return 0 if rep.passed else 1


def cmd_oidc_finish(args) -> int:
    from urllib.parse import parse_qs, urlparse

    try:
        L.require_live_authorisation(os.environ, flag=args.authorise_live)
    except L.LiveCheckRefused as exc:
        return _dry("redeem the Google authorization code through the real provider and validate PKCE, ID token and UserInfo subject", str(exc))
    from src.application.oidc import GoogleOidcProvider
    from src.core import secrets as S
    from src.invitations.policy import invitation_required

    saved = json.loads(Path(args.state_file).read_text())
    q = {k: v[0] for k, v in parse_qs(urlparse(args.callback_url).query).items() if v}
    if q.get("state") != saved["state"] or not q.get("code"):
        _emit({"error": "callback URL has no code or its state does not match the saved transaction"})
        return 1
    redirect = (os.environ.get("OIDC_REDIRECT_URI") or "").strip()
    cid, secret = S.read_setting("GOOGLE_CLIENT_ID") or "", S.read_setting("GOOGLE_CLIENT_SECRET") or ""
    import httpx

    def factory(rec):
        return GoogleOidcProvider(client_id=cid, client_secret=secret, transport=rec)

    rep = L.run_callback_check(factory, code=q["code"], redirect_uri=redirect, verifier=saved["verifier"], transport=httpx.HTTPTransport(),
                               invitation_required=invitation_required("staging"))
    Path(args.state_file).unlink(missing_ok=True)                    # single use: the verifier is spent whatever the outcome
    out = rep.to_dict()
    out["manual_followups"] = ["call the callback WITHOUT an invitation for an unknown Google account and confirm 403 invitation_required (see runbook step 5)"]
    _emit(out)
    return 0 if rep.passed else 1


def cmd_email_send(args) -> int:
    try:
        L.require_live_authorisation(os.environ, flag=args.authorise_live)
    except L.LiveCheckRefused as exc:
        return _dry("send ONE bounded test message through the real Brevo adapter to the address given with --recipient", str(exc))
    from src.mail.sender import BrevoEmailSender, EmailMessage, build_email_sender, send_detailed

    sender = build_email_sender()
    if not isinstance(sender, BrevoEmailSender):
        _emit({"error": "the Brevo adapter is not active (EMAIL_PROVIDER, BREVO_API_KEY, EMAIL_SENDER)"})
        return 1
    result = send_detailed(sender, EmailMessage(to=args.recipient, subject="Ask4Mo staging email check",
                                                body="This is a staging deliverability check. No action is needed.", category="admin_test"))
    if result.provider_message_ref and args.ref_file:
        _write_private(Path(args.ref_file), result.provider_message_ref)
    rep = L.Report("brevo_submission")
    rep.add("provider_accepted", L.PASS if result.status == "provider_accepted" else L.FAIL, result.failure_category or result.status)
    rep.add("message_reference_returned", L.PASS if result.provider_message_ref else L.FAIL)
    rep.add("delivered_to_inbox", L.NOT_RUN, "provider acceptance is not delivery: the operator confirms the inbox by hand, then the webhook proves it")
    _emit(rep.to_dict())
    return 0 if rep.passed else 1


def cmd_webhook_probe(args) -> int:
    try:
        L.require_live_authorisation(os.environ, flag=args.authorise_live)
    except L.LiveCheckRefused as exc:
        return _dry("POST signed, forged, old, replayed and malformed events to the staging webhook URL", str(exc))
    if not args.url.startswith("https://"):
        _emit({"error": "the webhook URL must be https"})
        return 1
    secret = (os.environ.get("BREVO_WEBHOOK_SECRET") or "").strip()
    if not secret:
        _emit({"error": "BREVO_WEBHOOK_SECRET is not set"})
        return 1
    import httpx

    ref = Path(args.ref_file).read_text().strip() if args.ref_file and Path(args.ref_file).exists() else "no-such-message@probe"
    mode = (os.environ.get("BREVO_WEBHOOK_AUTH") or "hmac").strip().lower()
    probes = L.build_webhook_probes(secret, message_ref=ref, mode=mode)

    def post(body: bytes, headers: dict) -> int:
        return httpx.post(args.url, content=body, headers={"content-type": "application/json", **headers}, timeout=10.0, follow_redirects=False).status_code

    rep = L.run_webhook_probes(post, probes)
    _emit(rep.to_dict())
    return 0 if rep.passed else 1


def cmd_redis_check(args) -> int:
    try:
        L.require_live_authorisation(os.environ, flag=args.authorise_live)
    except L.LiveCheckRefused as exc:
        return _dry("run distributed-limiter checks against REDIS_URL under a unique key prefix and delete exactly those keys", str(exc))
    from src.core import secrets as S

    url = (S.read_setting("REDIS_URL") or "").strip()
    if not url:
        _emit({"error": "REDIS_URL is not set"})
        return 1
    import redis

    rep = L.run_limiter_checks(redis.Redis.from_url(url, socket_timeout=2.0, socket_connect_timeout=2.0))
    _emit(rep.to_dict())
    return 0 if rep.passed else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("oidc-config").set_defaults(fn=cmd_oidc_config)
    p = sub.add_parser("oidc-start")
    p.add_argument("--state-file", required=True)
    p.add_argument("--url-file", required=True)
    p.set_defaults(fn=cmd_oidc_start)
    for name, fn in (("oidc-finish", cmd_oidc_finish), ("email-send", cmd_email_send), ("webhook-probe", cmd_webhook_probe), ("redis-check", cmd_redis_check)):
        p = sub.add_parser(name)
        p.add_argument("--authorise-live", action="store_true")
        if name == "oidc-finish":
            p.add_argument("--state-file", required=True)
            p.add_argument("--callback-url", required=True)
        if name == "email-send":
            p.add_argument("--recipient", required=True)
            p.add_argument("--ref-file")
        if name == "webhook-probe":
            p.add_argument("--url", required=True)
            p.add_argument("--ref-file")
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
