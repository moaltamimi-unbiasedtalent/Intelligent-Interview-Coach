# Checklist for the qualified legal review

For the person or firm the owner appoints (OD-LANG-04). This checklist is a worklist, not a conclusion. **Every box is unchecked and every sign-off below is NOT DONE.** Do not mark anything here as complete on a reviewer's behalf; the owner records a qualification outcome through the language readiness record (`docs/production/execution/language_readiness.json`, gate LG-10) with the signed qualification as evidence.

## A. Before reading any text

- [ ] Confirm the scope: the texts in `texts/en.md` sections 1 to 3 (Privacy, Terms, AI transparency), section 4 (Trust), section 5 (in-app Data & Privacy copy) and section 6 (AI-guidance and source wording).
- [ ] Read `FACTS.md` "Findings that need attention first" and confirm none is a misreading of the product.
- [ ] Decide the answers to `OPEN_LEGAL_QUESTIONS.md` (or mark each as deferred with a reason).

## B. Per document (review the source language first)

### Privacy
- [ ] Identity of the responsible party and the contact (OL-P1, OL-P2) are stated as counsel requires.
- [ ] Every category of data in "What we store" matches `FACTS.md` PF-01 to PF-09, and nothing material is missing (see DF-01 to DF-09).
- [ ] The processors and recipients are described as counsel requires (OL-P3, OL-P4), including the embeddings recipient (DF-02) and optional observability (DF-03).
- [ ] Voice statements are accurate and complete (PF-10 to PF-12), including that realtime voice is off by default and unverified live.
- [ ] Retention, export, deletion and backups wording is acceptable (OL-P5 to OL-P8) and matches PF-17 to PF-20.
- [ ] The wording about acknowledgement of document versions is acceptable (OL-P9).
- [ ] Rights wording and the access-request path are acceptable (OL-R2).
- [ ] Each proposal CL-02 to CL-11 is accepted, amended or rejected.

### Terms
- [ ] The plan and price wording is accurate for the product as it is when it ships (TF-05, OL-T1).
- [ ] Access during the private beta is described as required (OL-T2).
- [ ] Liability, warranty, governing law and consumer-rights wording are acceptable (OL-T3).
- [ ] Content licence and acceptable use are acceptable (OL-T4, OL-T5).
- [ ] Proposals CL-01 and CL-12 are accepted, amended or rejected.

### AI transparency and AI-guidance wording (K-AIGUID)
- [ ] The statements match `FACTS.md` AF-01 to AF-11, and the tool-revalidation sentence is accurate at publication time (AF-05, OL-A1).
- [ ] Labels and disclaimers in section 6 of each language file are acceptable (OL-A2, OL-A4, OL-A5).
- [ ] The "never infers" statements are acceptable (OL-A3).
- [ ] Proposal CL-13 is accepted, amended or rejected.

## C. Per language (after the source text is settled)

For each offered language, a qualified reviewer compares the translation with the approved source and checks legal equivalence, terminology and tone. The slogan "Ask More. Be More." is never translated.

- [ ] Meaning of every legal statement preserved, none added, strengthened or weakened.
- [ ] Defined terms consistent across the three documents.
- [ ] Banner, date line and placeholders (`{date}`) correct.
- [ ] Section 4 to 6 strings reviewed (Trust, Data & Privacy, AI guidance and the fixed Mo wording).
- [ ] The prevailing-language rule applied (OL-L1).

## D. Sign-off record (NOT DONE for every language)

No reviewer has been appointed or has signed anything. Do not edit this table to record a sign-off; record it through LG-10 with the signed qualification attached.

| Language | Privacy | Terms | AI transparency | Section 4 to 6 wording | Reviewer name and qualification | Date | Status |
|---|---|---|---|---|---|---|---|
| en (source) | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| de | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| fr | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| es | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| it | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| pt | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| nl | not reviewed | not reviewed | not reviewed | not reviewed | none appointed | none | NOT DONE |
| ru (preserved, not offered) | not applicable | not applicable | not applicable | not applicable | none | none | EXCLUDED |

## E. After approval

- [ ] Apply the approved source text through the legal document registry (new version, content hash, effective date) and the catalogues.
- [ ] Translate and review every offered language.
- [ ] Regenerate this pack (`python scripts/legal_review_pack.py --write`) so the manifest digests change with the text.
- [ ] Re-run the product's claim-discipline checks (no unsupported absolutes, no compliance claim that counsel has not approved).
