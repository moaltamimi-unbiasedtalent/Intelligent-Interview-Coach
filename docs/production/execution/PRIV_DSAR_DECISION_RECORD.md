# PRIV-DSAR decision record: how a data-access request is fulfilled

Package 05E (PG-04). Status: **OPEN, OWNER DECIDES.** This is an engineering decision record. It lists what can be built, what each option costs and risks, and a recommendation. It states no legal conclusion: what a data-access request legally requires (identity checks, deadlines, completeness, formats, exemptions) is a question for qualified counsel (see the 05E legal review pack, PR 2) and is not answered here. Nothing in this record claims GDPR or any other legal compliance.

## 1. Facts today (each verified in the code)

| Fact | Where |
|---|---|
| The candidate can download their own data at any time, immediately, as one JSON document (`ask4mo.candidate-export.v1`), built on demand, nothing stored, owner-scoped by the session | `src/application/data_export.py`, `GET /auth/account/export` |
| The export lists what it holds and what it does not (`scope.included`, `scope.not_included`) | `data_export.py` `INCLUDED`, `NOT_INCLUDED` |
| Not in the export: original uploaded files, security and audit records, other people's data, internal prompts, support staff's internal notes, the CONTENT of preparation-chat runs (identifiers and status only), acceptances from before recording existed | `NOT_INCLUDED` |
| A privacy request is a durable record for human follow-up. A `data_access` request is completed by recording `export_provided` (the candidate used the export) or `information_provided` | `src/privacy/requests.py`, `src/privacy/policy.py` |
| There is NO Admin export or download of candidate data and no secure artefact store. Admin sees metadata only; no break-glass, no impersonation | `docs/capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md` section 10, `CLAUDE.md` |
| A request from a person who cannot sign in (lost access, closed account) has no technical path: an operator can record it (`admin_recorded`) but cannot produce data | `PrivacyRequestService.create(... source="admin_recorded")` |
| Checkpoint (chat) content is readable only through the saver for one known run id; there is no export of it | `src/privacy/preparation.py` |

## 2. What an operator-side or asynchronous export would need (all missing today)

1. A secure artefact store with encryption at rest and a managed key (the encrypted `SecretStore` exists for credentials, not for large artefacts).
2. Identity verification of the requester that is stronger than "a signed-in session" for any path where the requester is not already the signed-in owner.
3. An expiry and deletion rule for the artefact, itself covered by the deletion safeguards (an export artefact is a new store that deletion must enumerate).
4. A completeness definition per store (SQL tables, private files, checkpoint content, indexes, backups) and a way to prove it, including chat content, which cannot currently be extracted.
5. Audit of every generation and download, metadata only.
6. A rule for what an operator may see. Any option in which an operator downloads the artefact makes Admin a content superuser, which the platform deliberately is not.

## 3. Options

| Option | What it is | Effort (engineering days, estimate) | New privacy risk | Notes |
|---|---|---|---|---|
| A. Status quo, hardened | Self-service export stays the only data path. A `data_access` request is completed by pointing the candidate to it. Close the known gaps (add chat content to the export, include version identity of acceptances, ship the 05E acceptance history) | 2 to 4 | None new | Works for signed-in candidates. Does not serve a requester who cannot sign in. Chat content export needs a saver-level read per indexed run (indexed runs only; the unindexed limit remains) |
| B. Candidate-initiated asynchronous export | The signed-in candidate asks for an export; a worker job builds it into the encrypted artefact store; only the candidate downloads it, once, within a short expiry, after a fresh password step-up. The operator never sees it | 6 to 10 | A new store (artefact) that must be encrypted, expire and be erased by account deletion | Useful if exports become large or must include chat content. Still requires a signed-in requester |
| C. Operator-generated export delivered through the candidate | An operator triggers the job for a verified requester (out-of-band identity check); the artefact is released only to the candidate through an authenticated link or channel; the operator never downloads it | 8 to 12 | As B, plus the out-of-band identity process and the release channel | Serves a requester who cannot sign in only if the owner defines an identity-verification procedure (a legal and operational decision) |
| D. Admin downloads candidate data | An Admin permission to generate and download a candidate's export | 4 to 6 | Makes Admin a candidate-content superuser; contradicts a standing platform rule | **Not recommended.** Listed only so the choice is explicit |

## 4. Recommendation

**Option A now, for the invitation-only private beta, plus the three closing items below; revisit B (and C only if counsel requires a requester path that does not depend on signing in) before general availability.**

Why: the private beta has invited, signed-in candidates who can already export everything the product can export, immediately. A, B and C add a new store and an identity-verification procedure that nobody can specify without the legal answers in section 5. D is rejected on principle.

Closing items to include whichever option is chosen (not built in 05E, so the decision stays open):

1. Preparation-chat content in the export (indexed runs only; the unindexed limit stays stated).
2. A written, operator-facing procedure for a requester who cannot sign in (who verifies identity and how; what is released and by which channel), approved by counsel.
3. The retention of the export artefact (none today: the file is built on demand and not stored) stays "not stored" unless B or C is chosen.

## 5. Questions that need counsel (not answerable by engineering)

- What identity verification is needed for a request from a person who is not the signed-in account holder?
- What must the response contain (categories, sources, purposes, recipients) beyond the JSON export, and in what form?
- Is "the candidate downloaded the export" an acceptable way to complete a request, and what record of it must be kept?
- Are chat transcripts (checkpoint content) within the scope of a request, and what is the position on content that cannot be enumerated (never-indexed runs, backups)?
- What response time applies, and how is it measured with an operator-recorded request?
- What is the position on third-party processors' copies (model provider, email provider) for an access or deletion request?

## 6. Owner decisions needed

| Id (proposed) | Decision | Default if undecided |
|---|---|---|
| OD-PRIV-DSAR-1 | Choose option A, B, C (D is not offered) | A for the private beta |
| OD-PRIV-DSAR-2 | Authorise engineering of the closing items (chat content in the export; procedure for a requester who cannot sign in) | Not authorised; the stated limits remain |
| OD-PRIV-DSAR-3 | Name who completes data-access requests operationally and who verifies identity | Unnamed; a `data_access` request is completed by pointing to the self-service export |

Counsel's answers to section 5 are an input to OD-PRIV-DSAR-1 and are **not** recorded here as done. Legal review (LG-10, PG-04) stays open.
