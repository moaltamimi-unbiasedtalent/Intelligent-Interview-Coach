# Ask4Mo Capstone — Evaluation Plan

Every major capability has a planned evaluation method. Not "test count". Deterministic where
possible; model-judged and paid runs are explicitly labelled and **require authorization**. Keep the
frozen historical retrieval suite separate from a new Capstone extension suite (a changed denominator
must not masquerade as improvement).

| Area | Metric | Fixture / dataset | Threshold | Det/Judge | Paid? | CI/Manual | Evidence |
|---|---|---|---|---|---|---|---|
| Agent goal completion | completion rate | scripted orchestration cases | maintain Sprint 4 gate | deterministic | free | CI | `scripts/eval_agent.py` |
| Tool selection | required/unnecessary rates | scripted cases | maintain | deterministic | free | CI | eval_agent |
| Multi-agent hand-offs (if built) | typed hand-off validity, budget/cancel | new specialist fixtures | define pre-P5 | deterministic | free | CI | new suite |
| RAG grounding / citation completeness | citation_completeness, no-fabrication | retrieval suite | 1.0 citation on supported | deterministic | free | CI | eval_knowledge_retrieval |
| Retrieval coverage / geography / unknown-role safety | rates | 81-case suite | maintain (0.914/1.0/…) | deterministic | free | CI | retrieval_after |
| Document extraction | extraction accuracy, provenance | synthetic PDF/DOCX/TXT | define | deterministic + human | free | CI + manual | AC-08 |
| OCR | correction burden, page provenance | scanned/image fixtures | define | human-checked | maybe | manual | EX-03 |
| Evidence/story provenance | source-linked, labelled drafts | fixtures | no unverified-as-fact | deterministic | free | CI | EX-08 |
| Speech transcription | WER vs reference, correction burden | EN/DE reference audio | define per-language | measured | live (auth) | manual | AC-13/23, EX-04 |
| Voice latency (if realtime) | p50/p95 with sample size | live sessions | define pre-test | measured | live (auth) | manual | AC-23 |
| Interview Practice | exactly-once answer commit | flow tests | pass | deterministic | free | CI | AC-14 |
| Progress / History | metrics match stored data | api tests | pass | deterministic | free | CI | AC-06, AC-04 |
| Memory | approval-only, scoped | tests | pass | deterministic | free | CI | AC-06 |
| Authorization / cross-user | ownership on all paths | two-user neg tests | 0 leaks | deterministic | free | CI | AC-02 |
| Workspace isolation / sharing / revocation | default-private, revoke works | two-team fixtures | pass | deterministic | free | CI | EX-06 |
| Basic/Premium enforcement | server-side gate | entitlement neg tests | 0 bypass | deterministic | free | CI | EX-09-style |
| Admin authorization | PLATFORM_ADMIN gate | admin neg tests | 0 escalation | deterministic | free | CI | new AC |
| Privacy export/delete | exact scope, no resurrection | lifecycle tests | pass | deterministic | free | CI | EX-01/10 |
| Prompt injection (incl. doc/OCR) | inert as data | injection fixtures | 0 exec | deterministic | free | CI | EX-03 |
| SSRF / external content | blocked private/redirect | ssrf suite | 1.0 | deterministic | free | CI | eval_external_research |
| Uploads | safe negative cases | corrupt/oversized/malicious | safe | deterministic | free | CI | AC-09 |
| RAGAS generation quality | ID precision/recall (det) + judge (paid) | fixed dataset | report, don't game | det + judge | judge PAID (auth) | manual | AC-22, EX-13.. |
| Performance | latency w/ sample size | representative | set pre-final | measured | free | manual | AC-23 |
| Accessibility | keyboard/contrast/states | key screens | pass | manual + e2e | free | CI+manual | AC-19 |
| Production smoke | health, auth, limits | staging | pass | live (auth) | live | manual | EX-12 |

**Paid boundary:** paid LLM, paid RAGAS judge, live STT/TTS/Adzuna/hosting/email calls = 0 unless the
owner explicitly authorizes for that specific run; record provider, scope, cap, count, result, config.
Set thresholds on the chosen laptop/provider **before** final evaluation; never relax them afterward.
