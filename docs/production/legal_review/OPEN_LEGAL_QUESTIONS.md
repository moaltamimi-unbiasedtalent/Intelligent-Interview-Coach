# Open legal questions

Questions that engineering cannot and must not answer. Each is a question for qualified counsel (or an owner decision where stated). Nothing here is a legal conclusion. Ids are referenced from `CHANGE_LIST.md` and `FACTS.md`.

## Identity and contact

| Id | Question |
|---|---|
| OL-P1 | Which legal entity operates the service and is the responsible party for personal data? What must the texts say about it? (No operator identity appears in the Privacy text today.) |
| OL-P2 | What privacy contact must be published, and is a data-protection officer or an EU/UK representative needed? (No contact address exists in the configuration.) |

## Recipients, processors and transfers

| Id | Question |
|---|---|
| OL-P3 | Which recipients and processors must be named or categorised (model provider via OpenRouter and the vendors behind it, an embeddings provider, Brevo, Adzuna, Langfuse if enabled, Google sign-in, a realtime voice provider if enabled, Stripe if billing is ever enabled, hosting provider)? Is a category list enough? See `FACTS.md` DF-04. |
| OL-P4 | What do the model and embedding providers do with request content (retention, use for training, location of processing), and what contract terms are needed? Are transfers outside the EU or EEA involved, and what mechanism applies? Engineering has not verified any provider's data terms. |
| OL-P10 | How should staff access be described? The application exposes metadata only to administrators; direct database or hosting-console access by an engineer is outside the application. |

## Content, retention and rights

| Id | Question |
|---|---|
| OL-P5 | Are audit identifiers (user id, request id, target ids) personal data for the purposes of the texts, and how long may audit and incident records be kept? |
| OL-P6 | How must backups be described, given that no code erases them and the hosting package has not defined them? |
| OL-P7 | Is it acceptable to disclose, as proposed, that preparation chats created before ownership recording and never reopened may not be found for deletion? What obligation attaches to content that cannot be enumerated? |
| OL-P8 | What retention periods apply to candidate content, authentication records, audit events, support tickets and any retained billing reference? (None is set; the product keeps content until the user deletes it.) |
| OL-P9 | What is the meaning and legal weight of the recorded acknowledgement of a document version? Is re-acceptance after a new version required, and how must it be collected? Registration records none today. |
| OL-R1 | Is there any processing that requires consent rather than another basis, and if so how must it be collected, recorded and withdrawn? (The product records no consent to optional processing.) |
| OL-R2 | What must a response to a data-access request contain, in what form and within what time, and how is the requester's identity verified when they cannot sign in? See the DSAR decision record `docs/production/execution/PRIV_DSAR_DECISION_RECORD.md`. |
| OL-R3 | Are Practice answers, CV content or documents likely to contain special-category data that users type voluntarily, and does that change the notice, the retention or the consent position? The product stores no protected trait deliberately. |
| OL-R4 | Are the practice scores and the Mo evaluation within or outside any rule on automated decision-making or profiling? The product states they are practice guidance, not a hiring decision, and no recruiter-facing ranking exists. |
| OL-R5 | Minors: is an age statement or an age gate required? No age check exists. |
| OL-R6 | What notice, if any, is needed for the single HttpOnly session cookie and for device-local voice preference storage? No third-party analytics script is loaded. |

## Terms

| Id | Question |
|---|---|
| OL-T1 | How should the plans be described while Premium cannot be bought? Is a price statement appropriate before payment exists? Which consumer rules on pricing, withdrawal and merchant of record apply once billing is enabled? |
| OL-T2 | Is the private-beta, invitation-only access something the Terms must state, and on what basis may access be withdrawn? |
| OL-T3 | Liability limitation, warranty disclaimer, governing law and jurisdiction: what is acceptable for consumers in each offered language's market? |
| OL-T4 | Content licence: what licence does the user grant for uploaded documents and generated content, and what does the service promise about ownership of outputs? |
| OL-T5 | Acceptable-use and abuse wording, and the right to pause or refuse service (the operator can pause capabilities). |

## AI transparency and AI guidance wording (K-AIGUID)

| Id | Question |
|---|---|
| OL-A1 | Is the sentence about allow-listed tools and server-side revalidation accurate enough to publish before package 01D is merged and verified? |
| OL-A2 | Which transparency obligations apply to a conversational AI coach and to AI-generated content (disclosure, labelling), and are the in-product labels (`provenance.*`, `trustUx.*`) sufficient? |
| OL-A3 | Does the statement that the product never infers emotion or traits from voice, and the absence of any such feature, match the classification counsel gives it? |
| OL-A4 | Source excerpts: what may be quoted from sources shown as evidence, how must licence and attribution be stated, and are link-out-only sources (Glassdoor, Kununu, Google, LinkedIn are not integrated) described correctly? |
| OL-A5 | Is the fixed Mo wording in every language (insufficient evidence, compensation guidance, unverified-general notice, model-unavailable fallback) acceptable as guidance wording? |

## Translations and process

| Id | Question |
|---|---|
| OL-L1 | Which language version prevails if translations differ? Is an engineering translation ever acceptable for a legal notice, and what qualification is required of the reviewer per language (OD-LANG-04)? |
| OL-L2 | How should the draft banner and the "last updated" date behave once counsel approves a text (and what version label and effective date does the legal document registry record)? |
| OL-L3 | What is the process for a legal text change after launch, and who approves it? |
