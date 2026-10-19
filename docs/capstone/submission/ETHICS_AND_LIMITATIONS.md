# Ethics, Privacy and Limitations

Drawn from the implemented behaviour and the deferred-issues register (`DI-` identifiers); claims stay within `docs/product/PRODUCT_CLAIMS.md`. Nothing here is legal advice or a compliance claim.

## 1. Ethical design decisions (implemented)

| Concern | What the system does | Evidence |
|---|---|---|
| Fabrication | Citations map only to retrieved evidence; unsupported markers are stripped; a money figure that appears in no evidence, tool result or the candidate's own words is removed; no unsourced compensation estimate is offered or stated; missing evidence produces an explicit abstention | grounding-policy tests (77), recorded-answer replay |
| Hiring decisions | Scores are practice feedback only; no hiring decision, no ranking of people; the product is not recruiter or ATS software | prompts, UI copy, 9 deterministic interview checks (no hiring-decision wording) |
| Bias and protected traits | No protected-trait inference; no personality, health or emotion diagnosis; no voice-based assessment; no camera or visual coaching; a deterministic bias-wording check exists in the interview harness (a proxy, not a bias audit) | design rules, tests |
| Candidate content as data | Job descriptions, backgrounds, documents, retrieved text and tool results are untrusted data in labelled blocks, scanned for prompt injection, never followed as instructions; candidate documents are never placed in a prompt | injection and trust-boundary tests |
| Human control | Real pause-and-resume for three decisions; nothing about the candidate is saved without approval; the approved handoff creates a session only in the frontend, never inside the agent | HITL tests |
| Privacy | Owner-scoped, private by default; export and deletion from the privacy centre; admins see metadata only and are never a private-data superuser; audit is append-only | privacy, isolation and admin tests |
| Transparency | The candidate is told Mo is AI and can be wrong; sources are shown only when retrieved evidence was used; a general answer to an external factual question without retrieval is labelled or the unsupported figure is removed | UI copy, policy tests |
| Language | Interface, conversation, dictation and geography are independent; a language choice never changes the labour market; Russian is interface and conversation only | i18n evaluator |
| Cost and abuse | Per-request token and cost caps, rate limits, a durable pause switch, a hard budget ledger for any live evaluation | tests, evaluators |

## 2. What data leaves the system

When live mode is enabled, prompts (including the candidate text the user typed or approved) are sent to OpenRouter and the model provider behind it. Candidate documents are not sent; only approved evidence and typed text can reach a prompt. The offline demonstration and every automated test send nothing. A data-processing review of the provider chain has not been done (`DI-K`, `DI-E`).

## 3. Known limitations (honest list)

**Quality evidence.** Live samples are small; no human has rated interview feedback, answer scores, citation support or translations (`DI-C`, `DI-L`); the deterministic checks are proxies. The live agent's tool selection is imperfect (0.773 on one 22-case run).

**Coverage.** The internal product-coverage gate fails: 386 of 412 developer-local (6 short of 392), 258 of 412 on a clean checkout, 0 human-qualified. The knowledge base is not committed; a clean checkout abstains. International compensation (Compensation V2) is built and **disabled**; only a US engineering package was isolated and no source is qualified for candidate-visible use; the seven knowledge-base languages are not seven supported markets (`DI-A`, `DI-B`).

**Grounding policy limits.** Detection is lexical, citation relevance is a shared-word proxy, a non-numeric unsupported claim is labelled but not removed, the agent verifies figures only against tool results and candidate text, and the final corrections were validated by deterministic tests but not by a new live run (`DI-D`).

**Privacy and legal.** Privacy notice, terms and AI-transparency pages are engineering drafts without legal review; selective preparation-chat deletion, bulk memory deletion and per-version document deletion do not exist; hosting backups would follow the provider's retention; legal-acceptance records are written only for new acceptances and never back-filled (PRIV-W9-01 and PRIV-W9-02 were closed in W10.10 with these stated limits) (`DI-F`, `DI-K`).

**Operations and integrations.** No hosted deployment, TLS, backup restore drill or monitoring was tested; a real malware scanner is not configured; the rate limiter is per-process unless an unvalidated Redis adapter is configured; Google sign-in and live email are not validated live; billing is a mock and Stripe has never been contacted; speech is browser-based, server speech is disabled and genuine Whisper or Kyutai execution is not verified (`DI-H`, `DI-I`, `DI-J`, `DI-E`).

**Accessibility and compatibility.** Browser coverage is chromium only; no real screen-reader testing or automated contrast audit; WCAG compliance is **not** claimed (`DI-G`).

**Process.** Acceptance criteria AC-03, 13, 18, 19, 22, 23, 24 and 25 are PARTIAL; AC-24's human revalidation (P10F) is deferred; no successor release candidate exists (RC-P10-004 was deliberately not created).

## 4. Lessons learned (material for the presentation)

1. A live run found two defects that unit tests could not: an import-time default that silently routed some requests to the wrong model, and a measurement harness that disabled retrieval and made the product look worse than it was. Correct the measurement before the product.
2. Citation syntax is not evidence: a valid `[1]` can sit on a sentence the source does not support, and another country's salary can look like support. Enforcement had to check scope, not just markers.
3. Small deterministic guards beat longer prompts for safety properties; prompts steer, code enforces.
4. Honest status labels (REAL, OFFLINE, MOCKED, LIVE, HUMAN) prevented several over-claims.

## 5. Where the full list lives

The deferred-issues register (`docs/capstone/POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md`, 394 issues: 342 active, 52 closed) and the acceptance ledger (`CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`). Deferral is scheduling only: nothing deferred is complete or waived.
