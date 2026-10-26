# POST272-03 — enforced CSP / Next.js hydration remediation

Baseline: main `992682c3fa9c891f5710c993e7d595f363b8c811`. Separate branch
`fix/nextjs-csp-hydration`; PR #273's campaign branch is inspected read-only and
is neither overwritten nor cherry-picked. Its final head `bc75b4c7` remains
unmerged with 27 PASS / 2 FAIL / 6 NOT RUN and Browser 667 PASS / 1 FAIL / 14 SKIP.

## Root cause and design

The shipped Caddy policy has `script-src 'self'`, while Next.js bootstrap/React
hydration and the theme initializer require inline scripts. The actual PR #273
built-image browser records 12 inline CSP refusals per page and a 45-second
sign-in UI timeout. HTTP transport success did not prove a working UI.

Middleware now generates an independent cryptographic 32-byte nonce per request.
It replaces client nonce/CSP values and forwards its enforced policy into SSR and
the response. Next.js attaches the nonce to its own scripts; the theme initializer
and static organization JSON-LD explicitly receive it. No untrusted markup is
mass-tagged with a nonce. `script-src 'self' 'nonce-<value>'` permits legitimate
bootstrap without authorizing arbitrary inline script; inline event handlers are
also refused. Script wildcards, unsafe-inline and unsafe-eval are absent. The
existing style directive is retained; other resource/security restrictions remain.

Caddy forwards the page policy and provides the old strict baseline only as a
deferred default when no upstream policy exists. It strips incoming CSP/nonce
headers; middleware independently replaces them. HSTS, frame, form-action, object,
permissions, MIME, referrer, cookies, CORS and trusted API proxy boundaries remain.
The configured public API origin is validated independently of request headers.

Root layout explicitly renders dynamically and responses are private/no-store.
Nonce-bearing HTML cannot be CDN/ISR/static/PPR cached or shared across responses.
Static assets retain caching. This is the supported Next.js 15 nonce rendering
model, with added per-request rendering work; no deployment is authorized.
Reference: https://nextjs.org/docs/15/app/guides/content-security-policy .

## Focused real-image qualification

The existing immutable-image CI job builds candidate API/web once and verifies
image/source metadata. It then builds the original-main frontend from committed
source and runs both through the actual respective Caddy files against the same
isolated real FastAPI/PostgreSQL authentication fixture. Reserved staging names,
internal CA, internal Docker network, no published ports, UID 10001 API / UID 1000
web, unique project/database and labelled resources only. No original environment,
database, candidate data or secrets are mounted. API budget remains CLOSED and
there are no provider keys or external container routes. Email is captured in
memory; actual invitation, registration, email verification and sessions are used.

Before-fix acceptance requires the original enforced header, observed inline
violations, no login request and no authenticated account UI. After-fix acceptance
requires usable hydrated sign-in, actual authenticated account UI and cookies,
history/opportunities rendering, fresh nonces despite forged request headers,
zero required-bootstrap refusals, nonce-less/replayed-nonce injection rejection,
real logout/session revocation and zero external request attempts. Original image
requests remain enabled; the unrelated existing network-idle test is unchanged.
Caddy validates both configurations. The driver verifies actual schema and running
image IDs and refuses non-owned cleanup. Only safe policy/status/count/hash JSON
is uploaded; synthetic credentials, cookies, raw service logs and traces are not uploaded; raw browser process output is
discarded so a failed form action cannot persist credentials. No framework/auth/security exception exists for tests.

Repeat after building a reviewed commit with the existing release builder:

```sh
python scripts/csp/qualify.py --execute-disposable \
  --manifest /absolute/release/release.json \
  --anchor REVIEWED_MANIFEST_SHA256 --sha REVIEWED_COMMIT \
  --out /absolute/new-output-directory
```

Local evidence: 1,547 frontend tests (including 13 CSP tests), production build,
TypeScript and lint pass. Focused Python auth/topology/hardening/harness: 82 pass;
10 harness guards (including credential-log suppression) pass. A local production-Next browser diagnostic
verifies 13 inline scripts carry the nonce, the theme initializer executes, no
bootstrap is refused, and an injected script is blocked; this is explicitly not
Caddy/real-authentication evidence. Ruff, 452-item reconciliation and evidence
consistency pass. Built-image before/after qualification and exact-head CI are
PENDING until the remediation PR's workflows complete. Native macOS/Docker-VM
full-image qualification is NOT RUN; Linux CI is authoritative. No unrelated
Docker resources are pruned. Current-head check results must not be inferred from
prior source results.

## First exact-source CI attempt (preserved)

Source `bc75a215f59aceee50d953a215501d8fa67f0a49`: full CI and all five
component workflows pass. Image run 40399666666 passes 16 image and 19 operator
checks, but stops before browser execution: the test-only TLS converter rewrote a
commented alternate Caddy example into an invalid directive. Safe artifact
12689741012 records FAIL; no connected sign-in result exists for that attempt.
Baseline web image `sha256:a19b7fcac8af1ba34615e1d7b5399556d707d7d2a9700f295643ea40c54463c9`;
candidate API `sha256:149e14126397625a466535f63e483c2257ea44738488bf484b34ac05cea83993`;
candidate web `sha256:96c9926af2321b0a33c43d1056006c208f88a526741b7ce17aee7eb83b9c60ce`;
manifest `f5c4e71b2d029e4cf32f58ea70edca5a490d5f4dac9f4c2aa76b4c9a798cb0a3`.

The converter now changes only actual configuration lines; comments/security
headers remain unchanged. Both original and patched fixtures pass actual local
Caddy 2.11.7 ARM64 validation in isolated containers. That bounded config check is
not Linux connected-image/auth qualification. Native full-stack testing remains
NOT RUN. Only the small pinned native Caddy image was added locally (capacity
checked first); no existing images/volumes/caches were pruned. Final-source CI is
required after this correction and API-origin/fixture-privacy hardening.

## Remaining scope and release status

Engineering integration remains 40/45. 00A/00B/07B/07C/08A stay open. Hosted staging,
human qualification, PG-01–PG-15 and LG-01–LG-14 approvals are unchanged; only the
historical PG-11 retains PASS. Zero languages are hosted-active. No production
readiness, AI quality, legal approval or language acceptance follows from a UI fix.

POST272-04 checkpoint reconnection remains OPEN and untouched. The primary Browser
E2E `/history` image/network-idle timeout remains OPEN and unchanged: no timeout,
wait condition, retry or image suppression has been introduced. PR #273's failed
historical evidence remains immutable. This patch does not close Task 07.

After review, merge and green main: prepare separate checkpoint repair; diagnose
the Browser image timeout separately; update PR #273 against reviewed merged fixes,
rebuild exact final-source images and rerun all mandatory full-stack/CI acceptance.
Close Task 07 only when every mandatory connected check passes. Do not start
Task 08, hosted deployment or live evaluation before that closure and approval.

Preservation baseline: all 45 original worktrees, 313 branch tips and 49 protected
files inventoried before creating the additional remediation worktree. Final
hash/status audit remains required before delivery. No original SQLite access,
paid provider, real email, owner budget marker, language activation, cloud/DNS,
registry publication, main push, force push or automatic merge is authorized.
