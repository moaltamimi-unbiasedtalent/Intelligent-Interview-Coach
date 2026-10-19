# P10E-R2: Approved Candidate Grounding Policies (corrective wave within P10E)

Status: IMPLEMENTED AND DETERMINISTICALLY TESTED; narrow live validation within the existing P10E ledger. Not accepted by the owner, not merged. Branch `fix/integrated-candidate-grounding-policy`, from `origin/main` `50aa2ef` (PR #202 merged by the owner). R2 is a corrective wave inside P10E, not a new top-level workstream; the 11-row tracker is unchanged. It prepares, but does not start, the integrated Candidate/Admin/Operations requalification.

## 1. Owner decisions (2026-10-19)

- **A. Contextual citations on abstentions.** A citation on an abstention is allowed when it is real, eligible, relevant context or explains the limit of the evidence; it must never imply an unsupported claim is verified, never cite unrelated passages, never present another geography's compensation as evidence for the requested one, and a coverage note is never positive evidence. Valid `[n]` syntax is not claim support.
- **B. Factual retrieval and clarification.** External factual questions (official statistics, occupation market figures, country salary, employment-market facts, regulatory requirements, published figures) must go through the existing `SearchCareerKnowledge` path before a verified claim. Insufficient evidence means: explain the limit, make no unsupported claim, offer a clarification or safe research guidance. Legitimate clarification without a tool call stays allowed (ambiguous role such as "PM", a plan requested with no identified gaps, a practice request with missing prerequisites); HITL stays for actions that need approval.
- **C. No unsourced compensation estimates** in all seven knowledge-base languages (en, de, fr, es, it, pt, nl). Russian stays outside the knowledge-base language set.

## 2. Implementation (one shared layer, no new citation system, no new RAG, no per-language engine)

| Piece | Location |
|---|---|
| Deterministic policy layer (classification into the six approved classes; enforcement of A and C; fabricated-figure rule) | `src/copilot/security/grounding_policy.py` (new, next to `output_guard.py`) |
| Career-chat wiring (after the existing `guard_output`; `trace.response_class`) | `src/copilot/service.py` (`answer()`) |
| Agent wiring (after the existing `guard_agent_answer`; policy B labelling; internal `response_class`, `policy_flags`) | `src/agent/grounding.py` (`apply_candidate_policy`), `src/application/agent_service.py` (`_to_result`), `src/agent/models.py` |
| Localized safe sentences (8 locales, bounded allow-list, engineering translations pending native review) | `src/copilot/rag/localized.py` (`COMPENSATION_GUIDANCE`, `UNVERIFIED_GENERAL`) |
| Prompt rules (retrieval requirement, clarify-before-guess, citation and estimate rules) | `src/agent/policies.py`, `src/copilot/rag/synthesis.py` |
| Prospective evaluation contract and evaluator | `evaluations/p10e/policy/`, `src/p10e/policy_evals.py`, CLI `scripts/p10e_live.py policy-*` |

Response classes: EVIDENCE_BACKED_ANSWER, ABSTENTION_WITHOUT_CITATIONS, ABSTENTION_WITH_CONTEXTUAL_CITATIONS, CLARIFICATION_REQUESTED, UNSUPPORTED_FACTUAL_RESPONSE, UNCERTAIN_REQUIRES_REVIEW (what cannot be decided deterministically is sent to review, never to success).

**Policy A in code.** Markers are removed (and only the markers) when they point at compensation evidence about a different geography than the resolved one, or, on an abstention or an uncovered compensation question, at evidence that shares no content word with the question. Relevant context citations stay, and the answer is then ABSTENTION_WITH_CONTEXTUAL_CITATIONS.

**Policy C in code.** When there is no in-scope compensation evidence, sentences that offer or give an estimate or range are removed (a refusal such as "I can't estimate" is kept; a sentence carrying a valid marker is kept) and one localized guidance sentence is added: how to find reliable sources and which details help (country, seniority, occupation). A money figure that appears in no evidence, tool result or the candidate's own words is removed with its sentence. A blank result becomes the localized insufficient-evidence sentence.

**Policy B in code.** The retrieval decision is the model's, steered by the strengthened agent prompt (a hard "MUST call SearchCareerKnowledge before a verified claim" rule with the owner's examples, and an explicit clarification exception). The deterministic safety net does not force a tool call (that would break the clarification exceptions); it labels a general answer to an external factual question that was given without retrieval, citation or abstention as not source-backed, and records a flag. A clarification or an abstention without a factual claim is never labelled.

Not weakened: injection screening, secret and leakage redaction, citation provenance, protected data, tool allow-list, cross-country evidence handling, HITL.

## 3. Before and after (deterministic)

Replay of the committed corrected R1 run (14 real model answers, no provider call, `tests/test_candidate_grounding_policy.py`):
- the 7 supported-definition answers are returned byte-identical (no valid evidence-backed text is damaged);
- 6 of 7 unsupported-country answers changed: the unsourced-estimate offer is removed (en, de, fr, es, it, pt); mis-attributed markers on the abstention are removed (en, fr, es); nl needed no change;
- no answer retains an estimate offer or a money figure.

Scripted answers in all seven languages (an abstention followed by an offer in that language, plus a refusal): offer removed, localized guidance added, abstention kept, refusal kept, no figure.

## 4. Historical evidence protection

The R1 registered records are immutable and untouched: `multilingual_cases.json` v1.0.0, `multilingual_corrected_v1.json` v1.1.0, `interview_cases.json`, the registration lock, and the run directories (the en, es and fr registered failures remain recorded failures; the post-hoc file stays labelled post-hoc). The new contract `evaluations/p10e/policy/candidate_policy_contract_v1.json` v1.0.0 is separate, prospective and hash-locked (`registration.lock.json`) before any live call; a test fails if it changes. Its results are written to their own run directories and are distinguishable by area (`policy-multilingual-live`, `policy-agent-live`).

## 5. Tests (all offline, no provider call)

`tests/test_candidate_grounding_policy.py`: 48 tests including cited abstention with relevant context; cited abstention with unrelated evidence; a US compensation citation never kept for a Canadian question (and kept for the US); missing-evidence explanation; evidence-backed answer unchanged; marker without evidence; unsupported and user-supplied figures; offer removal and refusal retention in all seven languages; 11 offer-versus-refusal sentences; the French year versus real amounts; localized text coverage and Russian exclusion; agent prompt rules; retrieval versus unlabelled clarifications (PM, missing gaps, handoff prerequisites); estimate offer after insufficient retrieval; agent figure verification; agent result integration; contract lock and non-interference with R1; compliance judgments (retrieval, clarification without retrieval, non-compliance, HITL expected and not applicable); owner-requested record fields; the replay of recorded real answers; no network call (httpx patched to fail); CI never references the live commands and the live commands refuse without `P10E_LIVE=1` and in CI.

Results: full backend suite 5,007 passed, 34 skipped, 0 failed (4,959 before R2; +48); Ruff and `git diff --check` clean; 22 evaluators, P10C-G and P10D (repeat 2) and the product-coverage guard pass; the 12-gate test passes. Frontend and browser tests were not run locally: no frontend file and no API schema changed (`response_class` is internal and a test asserts it is not in `AgentRunResponse`); GitHub CI runs them.

## 6. Narrow live validation (existing P10E authorization, host, ledger; nothing created or reset)

Ledger verified first: 270 calls, USD 2.02485575, 30 remaining. Executed 15 calls, all `openai/gpt-5.4`, 0 refusals, 0 unexpected model, clean checkout at `afb3ecf`, protected stores unchanged.

**Policies A and C, seven unsupported-country cases (the locked R1 inputs).** Per language, response class after enforcement: en, de, fr, es, it, pt, nl all ABSTENTION_WITH_CONTEXTUAL_CITATIONS; no estimate offer, no money figure, no cross-geography citation, answer language matched the question in all seven. The policy edited the model output in 6 of 7 (markers on all but de; an estimate offer in fr and pt); the strengthened prompt alone already stopped most offers. Language is a stopword proxy, not a fluency review; native review is PENDING_HUMAN_REVIEW.

**Policy B, four agent cases (contract cases, run once each).** pol-external-fact-retrieval: SearchCareerKnowledge used, COMPLIANT. pol-external-fact-no-evidence: retrieved, abstained without an invented statistic, COMPLIANT (the same goal skipped retrieval in both earlier R1 runs). pol-clarify-ambiguous-occupation: clarification without retrieval, no factual claim, COMPLIANT (recorded as a clarification without retrieval). pol-missing-plan-context: no tool, asked for the gap analysis inputs, but the judge cannot detect a request phrased without a question mark, so it is recorded REVIEW; nothing was changed after seeing it. Small sample, run once; consistency across repeats was not measured.

## 7. Cost and ledger

15 calls: provider-reported USD 0.0553, ledger committed USD 0.0876 (upper bound). The account usage delta for this batch was USD 0.0346 (6.7722 vs 6.7377), lower than the reported per-request sum; the account figure may lag or apply discounts and the difference is not attributed. Ledger now 285 of 300 calls, USD 2.11241325 committed, 15 calls and USD 7.88758675 remaining, no unknown or pending entries. USD 15 and any extra allowance were not used. Preserved: 4,096 output, 20,000 input, 60 s, 1 retry, concurrency 2, `P10E_LIVE=1` per run, no paid CI.

## 8. Known limitations and open defects

1. Detection is lexical (union of the seven languages): estimate offers, compensation and external-fact questions can be missed in unusual phrasing; sentence-level removal can drop a useful adjacent clause. Unclassifiable text is flagged for review, not judged.
2. The citation relevance test is a shared-content-word proxy; it is context-friendly by design and will not catch a relevant-looking but unsupportive citation (claim-level faithfulness remains an evaluation concern).
3. The agent's retrieval observation carries source metadata only, so a number in an agent answer can be verified only if a tool result or the candidate supplied it; the guard conservatively removes unverifiable figures. This is a pre-existing design limit, not changed here.
4. Policy B's retrieval decision remains model-driven; only labelling is deterministic. Live evidence is 4 cases, once.
5. The localized guidance strings are engineering translations pending native review. Human-reviewed quality: NOT VERIFIED.
6. L-XLANG-1 (native-phrasing cross-language retrieval) stays open; semantic live calibration and RAGAS live stay NOT RUN.

## 9. Capstone restrictions and status

All 12 rollout/billing gates False (test-verified); Compensation V2, Premium and speech providers disabled; no production, Stripe or live email; no real candidate data; no protected-store change; coverage unchanged (386/412 developer-local BELOW GATE, 258/412 clean-checkout, 0/412 human-qualified); AC-24 PARTIAL; P10C-F, P10F and the remaining W12.4E activation deferred.

## 10. Readiness

The three policies are implemented, tested offline and sampled live, and become explicit candidate acceptance criteria for the integrated requalification. R2 does not start it, does not create RC-P10-004 and does not begin P11. Pending: owner review, GitHub CI, and the remaining human review.

## 11. PR #203 enforcement review: confirmed defects and corrections (added after independent code review; sections 1 to 10 are unchanged evidence of the first delivery)

Starting head `0be2ce4`. Owner decision: the three policies were already approved; this corrects their implementation. No authorization, budget, ledger or host change; no live call was made.

### 11.1 Findings verified against the code

| # | Finding | Verified |
|---|---|---|
| 1 | The numeric allowance was built from ALL evidence text, including compensation evidence about another country. A Canadian salary of USD 85,000 backed only by US evidence lost its citation but kept the figure | Confirmed in `grounding_policy.enforce` (`corpus` included every `e.text`; the cross-geography marker was removed first, so the figure then looked supported). Reproduced by a new test before the fix |
| 2 | The estimate-offer guard skipped any sentence containing a citation marker (`not _MARKER_RE.search(sent)`), so "I can estimate a salary range [1]." survived | Confirmed |
| 3 | An unsupported external statistic answered without retrieval was only labelled ("not source-backed"); the statistic itself stayed in the answer | Confirmed in `apply_candidate_policy` |
| 4 | Metadata consistency: the agent kept `citations` and `sources` for markers the policy removed, and Career chat listed the removed evidence in `sources` | Confirmed (`_to_result` and `answer()` used the unfiltered lists; the API serialises `sources` from `response.evidence`) |

### 11.2 Exact corrections

1. **Scope-aware figures.** Compensation evidence about a different country than the resolved one is out of scope. Only in-scope evidence, tool results and the candidate's own words authorise a figure (money and, new, percentages). A foreign figure survives only inside a sentence that names its own country and states a limit ("the only compensation evidence is for the United States (USD 85,000), which does not establish Canadian pay"); a bare mention is not an excuse. The classification uses the same scope. When the answer is a compensation answer with no in-scope evidence, the evidence gap is always stated first and the localized guidance follows.
2. **A citation never authorises an estimate offer.** The marker exemption is removed. A sourced range for the correct country is untouched because in-scope compensation evidence disables the offer rule entirely.
3. **Conservative runtime safeguard for external facts without retrieval** (`src/agent/grounding.py`). For a recognised external-fact question answered without retrieval, a sentence that states a statistic (money, percentage, decimal, or number of three or more digits; years and list numbers are not figures) is removed and a localized, accurate evidence limitation is given ("I have not retrieved verified evidence ... tell me the country and the occupation and I can search"); general guidance without a figure is kept; it runs before the shared layer so the limitation is the true one (nothing was retrieved) rather than "the knowledge base lacks evidence". Clarifications, abstentions and no-tool turns are never touched and no tool call is forced. The percentage rule also applies after retrieval: a percentage that appears in no tool result is removed.
4. **One source of truth for citations.** `apply_candidate_policy` now returns the removed markers (`PolicyOutcome`). The agent drops those citations and their aligned sources from the result; the Career-chat response drops the evidence whose citation was removed, so inline markers, citation metadata and displayed sources agree. Retained contextual sources are untouched.

New localized text: `UNRETRIEVED_LIMITATION` (8 locales, engineering translations pending native review).

### 11.3 New regression cases (`tests/test_candidate_grounding_policy.py`, +29 tests)

Wrong-country figure without citation; contextual US-evidence limitation preserved and the bare-mention counter-case; matching-scope figure and sourced range preserved; candidate-provided figure repeated but never cited; cited estimate offer removed (English) and in all seven supported languages; unsupported statistic without retrieval removed; general guidance kept with only the figure removed; valid retrieval keeps its supported figure and a retrieved-but-unsupported figure is removed; unretrieved limitation in all eight locales and never an offer; four clarifications untouched; agent metadata consistency (citations and sources); Career-chat marker, citation and evidence consistency. The first delivery's 48 tests and the replay of the recorded real model answers still pass unchanged. No paid call; httpx is patched to fail in the no-network test.

### 11.4 Results

Full backend 5,036 passed, 34 skipped, 0 failed (5,007 before). Ruff and `git diff --check` clean. 22 evaluators, P10C-G, P10D (repeat 2) and the coverage guard pass. One evaluator (`eval_product_coverage`) failed once in the batch run immediately after the full suite and passed on five consecutive reruns (with and without these changes, exit code 0); the cause of the single failure was not captured and is recorded as an unexplained transient, not as a pass. Frontend and E2E: no frontend file or API schema changed, so the PR's fresh CI is relied on. Historical evidence unchanged: R1 files, run directories and the policy contract hash untouched. Ledger unchanged: 285 of 300 calls, USD 2.112 committed, 15 calls and USD 7.888 remaining. All 12 gates False; Compensation V2, Premium and speech disabled; coverage 386/412 developer-local BELOW GATE, 258/412 clean-checkout, 0/412 human-qualified; AC-24 PARTIAL; human-reviewed quality NOT VERIFIED.

### 11.5 Remaining limitations

1. The live sample in section 6 was taken BEFORE these corrections; no live call was made after them, so live behaviour of the corrected layer is covered by deterministic tests and the replay of recorded answers only.
2. Statistic detection is numeric and lexical: an unsupported external claim stated without any figure ("unemployment is low") is labelled, not removed.
3. The context-limitation exception depends on a small country-name table (US, CA, GB, DE, FR, ES, IT, PT, NL in the seven languages) and a limit-word list; an unlisted country or phrasing is treated as a plain foreign figure and removed, which errs on the safe side.
4. Agent figure verification is still limited to tool results and candidate text because the agent's retrieval observation carries metadata only (section 8, item 3).
5. Sources removed from the Career-chat `sources` are the ones whose citation the policy removed; other retrieved-but-uncited evidence is still listed as before.

### 11.6 Policy acceptance assessment

The three policies now hold at the figure, offer and metadata level, not only at the citation level. Pending: GitHub CI on the new head, owner review, human review of the localized text, and a live re-sample if the owner wants one (15 calls remain). Integrated requalification has not been started.
