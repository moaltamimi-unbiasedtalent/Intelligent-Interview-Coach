# Identity, email and rate limiting: live verification runbook and checklist (package 05D, PG-02)

Status of every live item in this document: **NOT RUN**. Nothing here has been executed against Google, Brevo or Redis. The offline engineering that makes
each step mechanical and safe is merged with the package; the live round trips wait for a hosted staging environment (OD-HOSTED) and the owner's authorisation.
Nothing in this document may be recorded as PASS until the lead has run the command on staging and kept its output.

## 0. Safety rules for the operator

- Run only on **staging**, only with the owner's authorisation, only from the repository root with the project interpreter.
- The script `scripts/verify_identity_live_05d.py` is a dry run unless ALL three hold: `--authorise-live`, `LIVE_VERIFY_AUTHORISED=I-AUTHORISE-STAGING-LIVE-CHECKS`
  and `API_ENV=staging`. Without them it prints what it would do and sends nothing. Production and local environments are always refused.
- Output contains check names, PASS / FAIL / NOT_RUN and bounded reasons only. It never prints a secret, token, code, PKCE verifier, ID token, email address, link,
  message content or Google subject (an 8 character hash prefix of the subject is the only trace).
- Use a **test Google account** and **the operator's own mailbox**. Never use a candidate's address.
- Credentials come from the staging environment or the Admin secret store, never from the command line.
- Do not flip any code gate without a separate owner decision (see section 6).

## 1. Preconditions (staging)

| Item | Setting | Notes |
| --- | --- | --- |
| Hosted environment | `API_ENV=staging`, https `APP_BASE_URL`, `FRONTEND_ORIGINS` | 05A staging compose |
| Invitation rule | automatic in staging (04E) | at least one unredeemed invitation for the positive path |
| Brevo | `EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, `EMAIL_SENDER` (a verified Brevo sender) | restart API and worker after any change |
| Brevo webhook | `BREVO_WEBHOOK_SECRET`, optional `BREVO_WEBHOOK_SECRET_PREVIOUS`, `BREVO_WEBHOOK_AUTH=hmac|bearer` | gate stays closed until section 5 |
| Google | `FEATURE_GOOGLE_LOGIN=true`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OIDC_REDIRECT_URI=https://<api host>/api/v1/auth/oidc/google/callback` | the redirect URI must also be registered in the Google client |
| Redis | `RATE_LIMIT_BACKEND=redis`, `REDIS_URL`, the `redis` package installed in the API image | a throw-away database/prefix |

Start-up refuses (critical) when a shared store is requested but `REDIS_URL` or the package is missing, and states the single-process limitation as a warning when
no shared store is configured (`RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED=true` records that the deployment is knowingly single-process).

## 2. Google sign-in (J-OIDC)

What is proved by the offline suite already: PKCE S256 with a fresh verifier, ID-token validation (RS256 only, iss, aud, azp, exp, iat, sub, at_hash), UserInfo `sub`
equal to the ID-token `sub`, strict boolean `email_verified`, trusted configured redirect in hosted environments, spent transaction cookies, and the
invitation-only rule for a NEW account, all against a mock Google. What only a real Google can prove: that Google's real responses satisfy those checks.

Steps:

1. `python scripts/verify_identity_live_05d.py oidc-config` (offline). Expect PASS for `google_sign_in_enabled`, `redirect_uri_trusted_https`,
   `invitation_required_in_this_environment`. Any FAIL: fix configuration first. With nothing configured the feature is **disabled** (fail closed): this is the
   default and the explicit disable path is `FEATURE_GOOGLE_LOGIN` unset or false (the sign-in routes then answer 404 and no cookie is set).
2. `python scripts/verify_identity_live_05d.py oidc-start --state-file /tmp/o.state --url-file /tmp/o.url` (offline). Checks host, S256 method, challenge equal to
   the saved verifier, state, redirect, client id, scope. Writes two 0600 files; the verifier is never printed.
3. Open the URL from the url file in a browser signed in to a **test Google account that has no Ask4Mo account**. After consent the browser lands on the callback
   (it may show an error page: that is fine, do not complete it in the app). Copy the full callback URL from the address bar.
4. `LIVE_VERIFY_AUTHORISED=I-AUTHORISE-STAGING-LIVE-CHECKS API_ENV=staging python scripts/verify_identity_live_05d.py oidc-finish --authorise-live --state-file /tmp/o.state --callback-url '<url>'`
   Expect `exchange_succeeded`, `token_request_sent_matching_verifier`, `id_token_validated`, `userinfo_subject_equals_id_token_subject`, `email_verified_strict`,
   `only_google_hosts_contacted` all PASS, and `invitation_only_new_account` PASS (the identity has no account, so it would be a registration that must be refused
   without a code). The state file is deleted on use. Record the 8 character subject hash with the result.
5. Invitation-only, end to end in the real app (manual, because it needs a browser): repeat steps 2 and 3 for the same Google account through the product start URL
   without an invitation and confirm the callback answers `403 invitation_required` and no account exists; repeat with a valid invitation (header
   `X-Invitation-Code` on `/api/v1/auth/oidc/google/start`) and confirm exactly one account and one redeemed invitation.
6. Disable drill: unset `FEATURE_GOOGLE_LOGIN`, restart, confirm `/api/v1/auth/oidc/google/start` answers 404.

Record NOT RUN until every step above has real output. Failure of any step means Google sign-in stays disabled for the beta.

## 3. Brevo submission (J-BREVO)

1. Confirm `EMAIL_PROVIDER=brevo` and the sender are verified in Brevo.
2. `LIVE_VERIFY_AUTHORISED=... API_ENV=staging python scripts/verify_identity_live_05d.py email-send --authorise-live --recipient <your own address> --ref-file /tmp/o.ref`
   One bounded test message is submitted. Expect `provider_accepted` PASS and `message_reference_returned` PASS. `delivered_to_inbox` is always NOT_RUN: confirm the
   inbox by hand. Provider acceptance is not delivery.
3. Registration and recovery round trip through the real UI/API with an invited test account: the verification link arrives, verifies once, a second use fails;
   `forgot-password` mail arrives, the reset works, old sessions end. Check `/admin/integrations/email_brevo/delivery` shows `provider_accepted` and no recipient.

## 4. Redis shared rate-limit store (J-RATE, J-REDIS, H-REDIS-LIVE)

1. Operator-provided throw-away Redis: `TEST_REDIS_URL=redis://... python -m pytest -p no:cacheprovider tests/test_redis_limiter_live_05d.py -q`
   (skipped, with an explicit reason, when the variable or the package is absent; nothing is installed or started by the suite).
2. On staging: `LIVE_VERIFY_AUTHORISED=... API_ENV=staging python scripts/verify_identity_live_05d.py redis-check --authorise-live`
   Checks two replicas share one window, retry-after, key independence, not degraded, window expiry; uses keys under a unique prefix and deletes exactly those.
3. Confirm the Admin readiness shows `shared_store_active` and not degraded; stop Redis and confirm the failure behaviour below, then restore it.

Failure behaviour as specified today (unchanged by this package): a bucket's `on_store_failure` decides. Every shipped bucket is `"local"`: the limiter degrades to a
bounded per-process window (never unlimited, never offline), reports `degraded`, and returns to the shared store when it answers again. `"deny"` (fail closed) exists
and is tested but no bucket uses it. Changing a bucket to `"deny"` is an owner decision.

## 5. Brevo delivery webhook (J-BREVO-HOOK)

The receiver is `POST /api/v1/mail/webhooks/brevo`. It is **non-operational** while the code constant `src.mail.webhook.DELIVERY_EVENTS_AUTHORIZED` is `False`
(every request answers 503 and nothing is stored). Authentication is HMAC (`X-Ask4Mo-Webhook-Signature: t=<unix>,v1=<hex>`, HMAC-SHA256 over `"<t>." + raw body`,
5 minute tolerance both ways) or a bearer secret (`BREVO_WEBHOOK_AUTH=bearer`). Which of the two Brevo can actually send must be confirmed on staging: that is the first
thing to learn from the live check. Only allow-listed events (delivered, soft bounce, hard bounce, blocked, spam) are applied, to a separate `delivery_state`; nothing else
(recipient, subject, link, tags, IP) is stored.

To run the live check the lead needs a staging build with the gate set to `True`. That is a code change requiring explicit owner authorisation and is not part of this package.
Then:

1. Create the webhook in Brevo pointing at the staging URL with the chosen authentication.
2. `python scripts/verify_identity_live_05d.py webhook-probe --authorise-live --url https://<staging api>/api/v1/mail/webhooks/brevo --ref-file /tmp/o.ref`
   (valid, replayed, forged, missing-signature, old-timestamp and malformed probes; expected 200, 200, 401, 401, 401, 400).
3. Send one real message (section 3) and confirm Brevo's real event arrives and `delivery_state` becomes `delivered` for that attempt only.

## 6. Owner decisions and gates that stay closed

| Item | State |
| --- | --- |
| `DELIVERY_EVENTS_AUTHORIZED` (`src/mail/webhook.py`) | False. Owner authorisation plus staging proof required to flip. |
| Google sign-in | Disabled by default. Enabling for the beta needs the section 2 results and the owner's decision; the frontend wiring is not part of this package. |
| Shared rate-limit store | Optional. Hosted multi-replica needs it; the failure policy per bucket is an owner decision. |
| Migration `0046_email_delivery_events` | Additive columns on `email_attempts`; downgrade refuses while any row carries delivery evidence. |

## 7. Results record (to be completed by the lead; do not edit before running)

| Check | Command | Result | Date | Operator |
| --- | --- | --- | --- | --- |
| Google round trip | section 2 | NOT RUN | | |
| Google invitation-only (new account) | section 2 step 5 | NOT RUN | | |
| Brevo submission | section 3 | NOT RUN | | |
| Brevo verification and recovery round trip | section 3 step 3 | NOT RUN | | |
| Brevo delivery webhook | section 5 | NOT RUN | | |
| Redis integration test | section 4 step 1 | NOT RUN | | |
| Redis staging check and outage drill | section 4 steps 2 and 3 | NOT RUN | | |
