# Ask4Mo v3: additional release acceptance gates

All checks begin **Not run**. These extend, rather than replace, AC-01–AC-25 in the original release checklist. C10 is existing functionality to preserve. Historical test passes do not certify the extensions.

| ID | Requirement/Task | Status | How/Evidence required |
|---|---|---|---|
| EX-01 | A9 report export/deletion | Not run | Owned report exports accurate Markdown/JSON; foreign IDs fail; deletion confirms exact scope, revokes access and records effects on shared links, checkpoints and backups |
| EX-02 | C1 realtime speech | Partial (P7.5) — deterministic sub-checks PASS; live round-trip NOT RUN | P7.5 delivers realtime architecture + deterministic proof: interruption/barge-in (response.cancel+truncate), commit-once/no-duplicate-answer, mic-denied/disconnect/unavailable fallback to turn-based, ephemeral-secret boundary, cross-user isolation — via `eval_realtime_voice.py`, `test_realtime_voice.py`, `realtime-voice.test.tsx`, `e2e/realtime-voice.spec.ts` (0 paid calls). STILL NOT RUN with a live provider: actual streaming round trip, real silence/timeout, real reconnect, and post-logout capture — no authorised realtime key (OpenRouter cannot serve realtime). |
| EX-03 | C2 OCR | Not run | Declared scanned-PDF/image fixtures produce reviewable text with page/source identity; unreadable/oversized/malicious inputs fail safely; correction burden measured |
| EX-04 | C3 multilingual speech | Not run | Actual English and German STT/TTS in dictation, recorded and realtime modes; per-language samples, accent limits, switching and browser coverage; no unsupported “all languages” claim |
| EX-05 | C4 additional specialists | Not run | Preparation and Evaluation specialists have distinct bounded duties; supervisor combines typed outputs; cancellation/budget/conflict tests pass; Practice retains state authority |
| EX-06 | C5 teams/sharing | Not run | Two teams plus personal accounts prove default-private records, explicit sharing, membership roles, invitation expiry and revocation across API/files/retrieval/jobs/caches |
| EX-07 | C6 social/email identity | Not run | Actual configured sign-in callback, verification and recovery delivery; token expiry/replay/linking tests; no account enumeration or open redirects; delivery/provider limitations disclosed |
| EX-08 | C7 story bank | Not run | User reviews source-backed stories, edits and reuses them in the right opportunity; unverified suggestions are labelled; deleted/revoked sources do not remain available as unqualified evidence |
| EX-09 | C8 operation model policy | Not run | Server allowlist prevents browser override; actual model/policy/rubric recorded; budget and fallback exercised; incompatible scoring versions are not pooled silently |
| EX-10 | C9 bulk cleanup | Not run | Dry-run manifest matches exact owned resources; active/held/pending items excluded; bounded idempotent batches handle failures/races; recovery and separate backup retention documented |
| EX-11 | C11 Prompt Lab | Not run | Candidate access denied; approved synthetic/evaluation data only; experiments isolated from live configuration; explicit version review before activation; real provider calls cost-gated |
| EX-12 | C12 hosted operation | Not run | Actual authorized deployment supports open verified-email registration with HTTPS, private storage, safe logs, signup/resend controls, per-user/global cost and concurrency limits; migration/restore/rollback and costly-feature pause exercised |
| EX-13 | K1 German compensation | Not run | Declared occupation set uses reviewed sources, terms, dates, geography and pay units; mapping/abstention cases pass without invented salaries |
| EX-14 | K2 credentials | Not run | Declared profession/jurisdiction coverage differentiates requirements and preferences, includes official lineage and dates, and abstains outside coverage |
| EX-15 | K3 emerging roles | Not run | Versioned aliases/context improve declared cases while preserving existing role resolution; ambiguous/new unsupported roles remain safe |
| EX-16 | K4 Adzuna extensions | Not run | Selected entitled operations work with bounded parameters and safe output; quota/failure/security tests pass; actual live validation and contract tests remain separately labelled |

## Evidence format

Record code SHA or dirty-diff identity, test date, environment, exact feature configuration, source/dataset/prompt/model versions, sample size, mode (mock/local/offline/live/human), result and limitation. Never include passwords, tokens, private audio or raw candidate data in shared evidence.

A mocked provider success does not satisfy an actual configured integration gate. A source download does not satisfy data licensing or quality acceptance. Public hosting cannot be marked complete from a local build or a deployment plan. Missing external credentials or owner approvals are reported as Blocked, not Passed.

## Amendments to the original checklist

- AC-09: supported scanned documents now take the OCR path; unreadable or unsupported files still require safe handling.
- AC-15/16: cover all four selected specialists and the supervisor, with deterministic enforcement outside model control.
- AC-02: extend ownership tests to teams, sharing, invited identities, exports, documents, stories and asynchronous work.
- AC-13/14/23: cover recorded and realtime modes plus the declared languages, separately from typed-input regression.
- AC-20/21: validate the selected local and hosted data, worker, checkpoint and recovery configuration.
- AC-25: show the actual delivery state of every selected extension and knowledge area. Do not claim all are shipped merely because they are now in the plan.
- A9 is no longer optional. C10 remains an existing baseline regression requirement. Paid RAGAS and optional external tracing remain separately approved validation choices.

## Release decision

The enlarged roadmap is approved scope. The date is still a target pending E0 feasibility. If required gates cannot be met by the planned freeze, escalate scope, capacity and schedule together. Only the owner can select a narrower review release or move the deadline. Until then, retain incomplete features visibly as incomplete rather than relabelling them deferred or complete.
