# R1.0 Scope Reclassification Proposal (PROPOSED, NOT APPLIED)

**Status:** PROPOSAL for owner confirmation, 2026-10-21 (Phase 00 review). The reconciliation file still lists all twelve candidates as R1.0 FIX BEFORE; nothing was moved. Historical issue IDs, failed gates and closure evidence are untouched: a confirmed move only changes the proposed release of an item, never its historical status. The rule applied: an item may leave R1.0 only if the capability it concerns is **provably inaccessible in the R1.0 Candidate API and UI** (REQ-DEFER-01, REQ-SCOPE-01).

## 1. Result

Of twelve candidates, **ten pass** and **two fail** the proof. If the owner confirms the ten, R1.0 must-fix goes from 88 to 78 and fix plus verify from 162 to 152. The two failures (BL-6.6, BL-7) stay in R1.0 and move into package 02E.

## 2. Evidence (machine-checked)

Each evidence key is verified by an offline test in `tests/test_r1_scope_exclusions.py` that runs in CI:

| Key | What is proven | Test |
|---|---|---|
| E-IMPORT | no module under src/ outside src/knowledge_foundation imports it (AST scan): the Compensation V2 and US occupational foundation code is unreachable from any API, application, agent or retrieval path | `tests/test_r1_scope_exclusions.py::test_e_import_*` |
| E-ROUTES | the OpenAPI path table (266 paths, 114 non-admin) has no compensation, foundation, qualification, alias or recording route | `tests/test_r1_scope_exclusions.py::test_e_routes_*` |
| E-UI | no frontend source (app, components, lib) references Compensation V2, the knowledge foundation, US SOC or BLS OEWS alias review | `tests/test_r1_scope_exclusions.py::test_e_ui_*` |
| E-READY | knowledge_foundation.readiness.assess reports operational_today False, 0 linkable Compensation V2 records and 0 approved Compensation V2 sources | `tests/test_r1_scope_exclusions.py::test_e_ready_*` |
| E-REGISTER | the register's own candidate-impact text records no Candidate effect while Compensation V2 and candidate-facing use stay disabled | `tests/test_r1_scope_exclusions.py::test_e_register_*` |
| E-SPEECH | the frontend never calls /speech/transcriptions or /speech/synthesis (only /speech/capabilities), the backend answers 503 speech_unavailable by default, and the server speech gate constants are False | `tests/test_r1_scope_exclusions.py::test_e_speech_*` |

How each proof reads in the product: **API** (E-ROUTES, E-IMPORT): the application exposes 266 OpenAPI paths, 114 outside Admin, none concerning compensation, the foundation, qualification, aliases or recording, and no runtime module imports `src/knowledge_foundation`, so no request can reach Compensation V2, the US occupational qualification or alias-review code. **UI** (E-UI, E-SPEECH): no frontend source mentions those capabilities, and the frontend only reads `/speech/capabilities`, so there is no server recording client to disable. **Gate** (E-READY, E-SPEECH): the foundation reports itself not operational with zero Compensation V2 records linkable and zero approved sources, and the server speech gate constants are False with the API answering 503 `speech_unavailable` by default (also covered by `tests/test_speech_w12_4e.py`).

## 3. The ten items proposed for reclassification

| ID | Title | Capability | Proposed release | Evidence |
|---|---|---|---|---|
| BL-5 | Review and decide the 12 measurement batches | 12 batches of Compensation V2 records awaiting reviewer decisions: Compensation Intelligence V2 work | R1.6 | E-IMPORT, E-ROUTES, E-UI, E-READY, E-REGISTER |
| BL-6 | Review the five alias proposals individually | Five US occupational alias proposals: qualified occupational sources for additional countries | R1.5 | E-IMPORT, E-ROUTES, E-UI, E-READY, E-REGISTER |
| BL-6.1 | Alias decision: Software Developer to 15-1252 | US alias decision Software Developer to 15-1252 | R1.5 | E-IMPORT, E-ROUTES, E-UI, E-REGISTER |
| BL-6.2 | Alias decision: Human Resources Manager to 11-3121 | US alias decision Human Resources Manager to 11-3121 | R1.5 | E-IMPORT, E-ROUTES, E-UI, E-REGISTER |
| BL-6.3 | Alias decision: Sales Manager to 11-2022 | US alias decision Sales Manager to 11-2022 | R1.5 | E-IMPORT, E-ROUTES, E-UI, E-REGISTER |
| BL-6.4 | Alias decision: Accountant to 13-2011 | US alias decision Accountant to 13-2011 | R1.5 | E-IMPORT, E-ROUTES, E-UI, E-REGISTER |
| BL-6.5 | Alias decision: Financial Analyst to 13-2051 | US alias decision Financial Analyst to 13-2051 | R1.5 | E-IMPORT, E-ROUTES, E-UI, E-REGISTER |
| BL-9 | Persistent-registry authorisation and promotion of us_soc_2018 and bls | Promotion of us_soc_2018 and bls_oews into the persistent source registry | R1.5 | E-IMPORT, E-ROUTES, E-READY, E-REGISTER |
| BL-12 | Separate runtime authorisation and deployment review for Compensation  | Runtime authorisation and deployment review for Compensation V2 | R1.6 | E-IMPORT, E-ROUTES, E-UI, E-READY, E-REGISTER |
| W12.4E-12 | Server-side browser recording client | Server-side browser recording client (server speech) | R1.4 | E-SPEECH |

Releases follow the agreed train: Compensation V2 work to R1.6, qualified occupational sources for additional countries to R1.5, server speech to R1.4.

## 4. Candidates that fail the proof (stay in R1.0)

| ID | Title | Why |
|---|---|---|
| BL-6.6 | Data Analyst and Product Manager remain unresolved | Data Analyst and Product Manager remain unresolved: the register states it affects 13 of the 26 insufficient coverage cases (ambiguous titles), i.e. the enabled role-resolution and abstention behaviour Candidates use today; the proof fails, so it stays in R1.0 (package 02E) |
| BL-7 | Resolve Data Analyst / Product Manager evidence gaps | Resolve the Data Analyst and Product Manager evidence gaps: needed for any legitimate coverage close and concerns enabled role resolution; the proof fails, so it stays in R1.0 (package 02E) |

## 5. What the reclassification does NOT exclude: unqualified US labour-market claims

The owner asked that unqualified US labour-market claims be excluded. The ten items above concern the *foundation* (Compensation V2 and US occupational qualification work), which is inaccessible. The **curated legacy corpus is a different capability and is NOT excluded**: it still carries US sources (O*NET, BLS Occupational Outlook Handbook narratives) and the compensation store holds only US (BLS OEWS, 1,386 records) and UK (ONS ASHE, 527 records) data, with no EU market records. A keyless, offline retrieval probe on the review data returned a BLS OOH passage for a UK nurse question, so a Candidate can receive US-sourced content for a non-US question. Excluding it needs engineering and a decision, not a reclassification:

- **02D** adds the approval filter so only qualified, licensed sources for enabled markets reach Candidate retrieval (REQ-COV-02), with the test that a Candidate cannot retrieve an unqualified source.
- **OD-US-CONTENT** decides whether US content stays enabled for Candidates, is limited to labelled general guidance, or is disabled in the EU beta.
- BL-8 (legal review of commercial use of BLS content outside the US) stays an R1.0 fix because the corpus is enabled today.

Until 02D lands, the claim "no unqualified US labour-market claim reaches a Candidate" must not be made.

## 6. What the owner must confirm

1. Move the ten items to their proposed releases (reconciliation regenerated with explained deltas; packaged as 00B).
2. Keep BL-6.6 and BL-7 in R1.0 (package 02E).
3. Decide OD-US-CONTENT, which governs section 5.

## 7. Preservation

All 394 historical issue IDs, the failed 95% coverage gate (386 of 412 against 392), AC-24 PARTIAL, human-qualified coverage 0 of 412 and every closure evidence remain exactly as recorded. The register file is not modified.
