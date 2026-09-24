# Ask4Mo Capstone — Provider & Build-vs-Buy Decisions

BUILD / LIBRARY / PROVIDER / DEFER for each new capability. EU/Germany-aware; reuse existing infra;
no provider chosen for fashion. All choices are **recommendations for E0** — no activation, no paid
or live calls, no account creation in P0/E0. Every provider needs a local-dev + mock path and
fail-safe behaviour.

| Capability | Decision | Recommended approach | Rationale / EU note | Cost | Risk / lock-in |
|---|---|---|---|---|---|
| Authentication | LIBRARY (build on) | Own email/password + sessions using a vetted library (e.g. Authlib/passlib) over existing FastAPI + `users`; keep transitional subject during migration | Full control of EU data; no vendor lock-in; integrates with existing scoping | low | low |
| Email verification | LIBRARY + PROVIDER | App-issued expiring single-use tokens + a transactional email provider | anti-enumeration, single-use tokens | free tier | provider swap easy |
| Password recovery | LIBRARY | Same token model as verification | single-use, expiring | low | low |
| Social login | PROVIDER (one) | One IdP (e.g. Google) via OIDC; verify email claims or run own verification; preserve local login | never link on unverified email match | free | medium (scope to one) |
| File/object storage | PROVIDER or LIBRARY | S3-compatible (EU region) or local disk in dev; abstract behind a storage interface | EU region before real content | usage-based | low (interface) |
| Document extraction | LIBRARY | Native text extraction (pypdf / python-docx / text) first | no OCR needed for native text | free | low |
| OCR | LIBRARY or PROVIDER | Bounded OCR worker (Tesseract self-host, or a provider) **only** for scanned/image inputs | privacy: prefer self-host; provider needs DPA | low–med | medium |
| Speech-to-text | PROVIDER | Managed STT with EN/DE (candidate: existing `google-cloud-speech` extra, or Deepgram/Whisper API); evaluate on real samples | EU data handling; per-language quality | per-minute | medium |
| Text-to-speech | PROVIDER | Managed TTS EN/DE for spoken questions | quality/latency | per-char | medium |
| Realtime voice | DEFER (after recorded) | Streaming provider only after recorded→STT→eval slice is stable | complexity/cost | per-minute | high |
| Email delivery | PROVIDER | Transactional email (e.g. Postmark/SES/Resend), EU-aware | deliverability, limits | free tier | low |
| Hosting | PROVIDER | Reproducible HTTPS host for Next.js+FastAPI (EU region), private staging first | EU region; rollback | usage | medium |
| Database | REUSE | SQLite dev → managed Postgres prod (Alembic already prod-ready) | already supported | usage | low |
| Background jobs | LIBRARY (minimal) | Bounded worker for OCR/cleanup (in-process/queue); avoid heavy infra early | operational simplicity | low | low |
| Rate limiting | LIBRARY | Server-side per-user + global limits + pause switch | abuse/cost control | free | low |
| Analytics/observability | REUSE | Existing provider-neutral sink + optional Langfuse (OFF default) | already privacy-safe | free | low |
| Error monitoring | DEFER/LIBRARY | Structured logging now; optional monitor later | keep logs sanitised | free | low |

**LLM:** REUSE OpenRouter via the existing model registry (Fast/Balanced/Advanced). No new LLM vendor.
**Adzuna:** REUSE existing bounded integration; K4 adds only entitled operations after verifying terms/quota.
Activation of any paid/live provider requires explicit owner authorization at the relevant phase.
