# Ask4Mo: Canonical Candidate Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `c69334ba3a7c74a60ad888914221be3e8ce52e25` (2026-10-13).

For the control-plane / operator side, see [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md) and the specialist Admin roles in [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md).

This document describes what the candidate product does today. It was written from the current code (routes, components, services and deterministic tests), not from planning documents. Where code and an older document disagree, the code is followed and the disagreement is listed in section 17. It documents current behaviour only: nothing here is aspirational. Externally meaningful sentences are constrained by [`docs/product/PRODUCT_CLAIMS.md`](../../product/PRODUCT_CLAIMS.md) (claim ids such as CLAIM-003 are cited where they apply). The protected slogan is **Ask More. Be More.** and is never translated or re-punctuated.

## 1. Who the candidate is
A candidate is a person preparing for one specific job interview, usually more than one at a time. They are not a recruiter, a hiring manager or an employer representative, and Ask4Mo is not a recruiter or applicant-tracking product. The candidate wants three things in one place: a clear picture of the role and company, honest practice, and a record of how they are doing, with control over their own data.

The mental model is **one job at a time**. A job lives in an **Opportunity**. Everything else (company research, preparation with Mo, practice, reports, progress) is organised around it.

## 2. Product promise
Ask4Mo is an AI-assisted interview preparation platform that organises preparation, practice and feedback around one job at a time.

Keep everything for one job in one place: prepare with an AI coach, practise realistic interviews and see your progress, with your data under your control.

**Mo is AI and can make mistakes.** Mo is the candidate-facing AI coach. Mo is not a recruiter, a hiring manager, a human coach or an employer representative, and Ask4Mo does not make hiring decisions. Ask4Mo shows sources when an answer uses career evidence, keeps data private by default, and lets the candidate download their data and remove individual items.

## 3. Journey map

```
Discover -> Account -> Onboarding -> Opportunity -> Context & Evidence
   -> Prepare with Mo  (+ Company research where useful)
   -> Practice -> Feedback / Deep Dive / Report
   -> Progress / History -> Return / Continue (back to Opportunity or Prepare)

Supporting flows:  Workspaces & sharing | Support | Data & Privacy | Trust | Settings
```

### Opportunity is not a Workspace (non-negotiable)
| | **Opportunity** | **Workspace** |
|---|---|---|
| What it is | The candidate's **private** preparation context for **one job** (role, company, optional job description) | A **collaboration** space for sharing selected items with other people |
| Organises | Company research, Prepare, Practice, reports and progress for that job | Nothing of the candidate's preparation by itself |
| Created automatically? | No Workspace is ever auto-created by an Opportunity | Only created explicitly by a person |
| Shared by default? | No. It is never shared by default | No. Joining shares nothing |
| Access to others | None | Only through explicit, **view-only** share grants on selected items |
| Required? | Not required to use Prepare or Practice | Not required for anything |

Membership of a Workspace does not expose a candidate's CV, reports, Story Bank or preparation content. Only an explicit grant on a specific item does (section 4, stage 13).

## 4. Stage-by-stage journey
Sixteen stages. Each lists purpose, candidate action, system behaviour, AI involvement, data used and created, persistence, privacy boundary, next action, routes and limitations.

### Stage 1. Discover
- **Purpose:** understand what Ask4Mo is before signing up.
- **Candidate action:** read the public pages.
- **System behaviour:** public routes are `/` (home), `/product`, `/pricing`, `/trust`, `/ai-transparency`, `/privacy`, `/terms`, `/about` and `/help`; `/getting-started` permanently redirects to `/product#how-it-works`. The home page presents one Opportunity holding the role, company, evidence, Mo preparation and practice, private by default, free to start with no credit card.
- **AI involvement:** none on the public pages. They state that Mo is AI.
- **Data used / created:** none about the visitor beyond ordinary page serving; no tracking of clicks or page views is claimed.
- **Privacy / trust boundary:** no testimonials, ratings, customer counts or outcome guarantees. Employee-review sites are not presented as sources.
- **Next action:** `/register`.
- **Limitations:** Pricing shows Basic (EUR 0) and Premium (EUR 19.99 per month). Premium is a **preview**: `BILLING_ENABLED` is false and the account page says Ask4Mo does not currently offer purchases, checkout or live payments (CLAIM-020). The pricing page wording and the account wording differ; see finding D-02.

### Stage 2. Register and sign in
- **Purpose:** create a private account.
- **Candidate action:** register with name, email and a password of at least 10 characters; verify the email; sign in; recover a forgotten password.
- **System behaviour:** `/register`, `/sign-in`, `/verify-email`, `/forgot-password`, `/reset-password`. Verification and reset emails arrive in the candidate's interface language (eight languages); a link is single-use, a used, expired or invalid link each gets its own message, resend has a one-minute cooldown, and a successful password reset signs the account out everywhere. Registration and recovery answers are identical whether or not an email is known. Sessions are server-side in an HttpOnly cookie. In production, a request without a session is refused (fail-closed); the anonymous developer identity exists only in development and test environments.
- **AI involvement:** none.
- **Data created:** account, hashed password, session records, audit events (metadata only).
- **Privacy / trust boundary:** Admins see account metadata only, never preparation content.
- **Next action:** onboarding.
- **Limitations (truthful status):** email and password are implemented. **Google sign-in is not available to candidates:** the backend flow exists but is off by default (it needs a feature flag and provider credentials), there is no Google button in the frontend, and it has not been validated live. Sign-in does not currently require a verified email. Live email delivery has not been validated (W12.4C). Rate limiting is in memory per process; a shared Redis adapter exists but is optional and has not been validated live.

### Stage 3. Onboarding
- **Purpose:** set Mo up around the candidate. A first-run gate sends an account whose onboarding is not complete to `/onboarding`; progress is saved on the server so an interrupted flow resumes.
- **Candidate action (7 steps):** Welcome; About you (preferred name, optional); Career focus (target role and career geography, both optional); Coaching (coaching style supportive, balanced or direct, default balanced; response detail Brief or Detailed); Language (interface language, Mo conversation language and dictation language); Privacy and memory (an explanation, nothing is saved); Review (edit any answer, then finish).
- **System behaviour:** answers are stored as account preferences and can be changed later in Settings. On finish the candidate is offered "create an Opportunity", a tour and Workspaces. Nothing in onboarding is mandatory except finishing the flow.
- **AI involvement:** none. Coaching style changes the **tone** of Mo's coaching prose only. It never changes scoring, evidence, difficulty or grounding.
- **Data created:** preferences (name, target role, geography, coaching style, response detail, interface and conversation language). The dictation language is stored **on the device** (browser storage), not on the account.
- **Language and market are separate dimensions.** The following never imply one another: **interface language**, **Mo conversation language**, **dictation language**, **text-to-speech / realtime language**, **document language**, **knowledge-base language**, **labour-market geography** and **taxonomy language**. Choosing a language never changes the career geography; geography is only ever set explicitly. Eight languages are available for the interface and for Mo's conversation: English, German, French, Spanish, Italian, Portuguese, Dutch and Russian (CLAIM-014).
- **Russian boundary:** interface YES, Mo conversation YES; dictation NO, text-to-speech NO, realtime voice NO, document reading (OCR) NO, knowledge base NO, official ESCO taxonomy NO; Russia is not a supported market and is never inferred from the language. The Russian interface is an engineering translation pending native and legal review.
- **Next action:** create an Opportunity (`/opportunities?create=1`).
- **Routes:** `/onboarding`, `/settings`.

### Stage 4. Create or select an Opportunity
- **Purpose:** give one job a private home.
- **Candidate action:** create an Opportunity with a **role** (required), and optionally a label, company, location, country, company website, a job description chosen from their own documents, and notes. Open an Opportunity from the list; move it between active, interviewing, offer, closed and archived; archive or delete it.
- **System behaviour:** the Opportunity home offers Company research, Prepare, Practice and Evidence for that job, shows how many interviews are linked, and suggests a next step (add a job description, then practise, then review history). Selection is carried in the URL (`?opportunity=<id>`); there is no global "current Opportunity" setting. A job description must be one of the candidate's own documents of category job description.
- **AI involvement:** none to create or edit.
- **Data used / created:** role, company and optional text the candidate typed; a link to a chosen job-description document. No CV or evidence text and no research content is copied into the Opportunity.
- **Persistence:** durable, owner-scoped.
- **Privacy boundary:** private to the candidate. It is never shared and never creates a Workspace.
- **Precedence:** **an explicit choice made in the session wins, then the Opportunity's context, then the account preference, then the default.** The Opportunity only **pre-populates** empty fields in Company research, Prepare and Practice; it never silently overrides something the candidate already entered, and it carries no language or geography.
- **Deleting an Opportunity:** deleting it **does not delete** interviews, reports, documents or evidence. Linked interviews and reports stay in History, unlinked from it; a linked job-description document stays. Deleting a job-description document clears the link and the Opportunity survives.
- **Limitations:** the interface edits an Opportunity's status; changing its other fields after creation is available in the API but not currently exposed as an edit form (finding D-06).
- **Routes:** `/opportunities`, `/opportunities/[id]`.

### Stage 5. Context and evidence
- **Purpose:** let the candidate bring their own background, privately, and decide what Mo may use.
- **Candidate action:** upload documents (CV, job description, portfolio or project, company or interview brief, other); review the extracted items one by one; build stories.
- **System behaviour:** PDF, DOCX, TXT, PNG and JPG up to 10 MB and 50 pages are accepted. Text is read directly; scanned files need OCR, which is a separate runtime that may not be enabled (the candidate is told, and can retry later). Extraction is **rule-based, not model-generated**: each item is a verbatim span with a page or section location, shown as **Extracted from your document**. Each extracted item is reviewed by the candidate: **Not reviewed yet** (pending), **Reviewed by you** (accepted), **Corrected by you** (edited) or **Rejected by you**. Nothing becomes reusable evidence until the candidate approves it.
- **Story Bank:** reusable interview examples built from **approved** evidence. A story shows how it came to be: **Built from your evidence**, **Written by you**, **Edited by you** or **AI suggested**. Its support is shown as **Supporting evidence available**, **Supporting source removed** (the source document was deleted or revoked) or **No supporting source**. Drafts are built deterministically from the candidate's own verbatim text.
- **"Reviewed by you" means exactly that.** It means the candidate reviewed the item. It does **not** mean a third party verified it. The phrase "Evidence verified" is not used as a candidate-facing claim.
- **AI involvement:** none in extraction or story drafting. Uploaded documents are untrusted data and are never placed in a model prompt. Mo can only use evidence the candidate has **approved** (stage 6).
- **Persistence:** original files and extracted items are stored privately for the owner and are never at a public URL. The candidate can download a document, retry processing, replace it with a new version, or delete it (deleting removes the file, extracted text and items; stories built from it lose their source and say so).
- **Limitations:** OCR live quality is unvalidated and Russian documents are not supported. Reviewing an item is not a check of its truth.
- **Routes:** `/documents`.

### Stage 6. Prepare with Mo
- **Purpose:** the central stage: understand the role, compare it with approved evidence, get a plan and tailored questions.
- **Candidate action:** describe the interview being prepared for (optionally pre-filled from an Opportunity and a chosen job description), converse with Mo over several turns, approve or reject Mo's proposals, and when ready start Practice.
- **System behaviour:** Mo is a stateful, bounded agent with a fixed step budget per turn. The conversation can be refreshed or resumed through the run id kept in the page address (`/prepare?run=...`). When the Agent Coach is not enabled on a deployment, `/prepare` falls back to the original deterministic coach (a safe rollback, not a candidate setting).
- **AI involvement:** Mo's prose is model-generated. Behind Mo sit exactly **three bounded specialists**: **role_opportunity** (reads the role), **candidate_evidence** (deterministic, selects only the candidate's **approved** evidence for the signed-in owner) and **interview_strategy** (maps evidence to what to practise, and asks rather than invents when evidence is missing). **There is no Evaluation specialist.** The agent can call exactly **11 registered tools**: six career tools (job-description analysis, gap analysis, preparation plan, interview questions, career-knowledge search, current-market research), the three specialist tools, and two human-action tools (propose memory, request practice hand-off). These are controlled capabilities, not separate user-facing agents, and the candidate never sees low-level stores.
- **Retrieval:** Mo searches the career knowledge base only when useful and states when evidence is insufficient instead of inventing an answer. Retrieved content is data, never instructions.
- **Human approvals:** exactly three decisions pause the run for the candidate: **confirm the role** when it is ambiguous, **approve a memory** (with an option to edit it before saving) and **approve the hand-off to Practice**. Nothing is saved or started without approval, and approvals apply once.
- **Data used:** the role and job description the candidate supplied; approved evidence (via the evidence specialist); approved saved memories (loaded as data, never as instructions); retrieved career sources.
- **Data created:** the Mo conversation for the run (kept so the run can be resumed; individual chats cannot currently be removed one by one from the interface); approved memories; optionally a Practice session created at hand-off.
- **Provenance labels (see section 6):** every Mo answer is labelled **AI-generated**.
- **Next action:** Practice (via the approved hand-off), or Company research.
- **Limitations:** the quality of Mo's live model answers is not measured by the deterministic tests. Mo can be wrong.
- **Routes:** `/prepare`, `/review/agent?run=` (the candidate's own run details), `/sources`.

### Stage 7. Company research (supporting flow)
- **Purpose:** gather checkable facts about an employer. It is a supporting flow, not the organising object (the Opportunity is).
- **Candidate action:** enter the company name and, to research the company's own site, its **official website**; optionally location, country, role and job description.
- **System behaviour:** research runs only against an explicit, validated website; a name alone returns a request to say which company, and **a domain is never guessed**. The report keeps three kinds of statement apart: **Fact** (stated by an official or company source), **Review** (third-party opinion, link-out only where lawfully available) and **AI suggestion** (a deterministic suggestion derived from the sources, never a company fact). A job-market lookup runs only when a role is given and only if the provider is configured.
- **AI involvement:** none in this report; the suggestions are rule-based.
- **Boundaries:** research is bounded and is not unrestricted web browsing; it does not claim real-time company intelligence. Glassdoor, Kununu, Google and LinkedIn are **not integrated** (a search link only, nothing copied). Company names are never translated, and the interface language never decides the geography.
- **Gating:** the capability is part of the Basic plan, can be paused by the operator, and is cost-limited. A paused platform shows a fixed message and the candidate's saved data stays available.
- **Persistence:** the report is not stored as part of the Opportunity (only a short-lived cache exists on the server).
- **Routes:** `/company`, `/company?opportunity=<id>`.

### Stage 8. Practice
- **Purpose:** rehearse a realistic interview.
- **Candidate action:** set up a session (target role, industry, optional job description, whether to use approved evidence, career level, number of questions, language, and optionally question types and difficulty), read a question, **type** an answer (or **dictate** it where supported), submit, read the feedback, optionally go deeper, move to the next question, and finish.
- **System behaviour:** sessions are durable and owner-scoped. The page address carries the session (`/practice?session=<id>`), so a refresh restores it. If a step is interrupted the candidate sees that the interview is saved and can **Resume** it when the failure is recoverable, or leave and return later from History or the Return card. Starting from Prepare or an Opportunity pre-fills the setup.
- **AI involvement:** the interviewer's questions, the answer evaluation and the final report are generated by a model. The model is told the conversation language and the coaching style as tone only.
- **Typed and dictated answers:** dictation (where the browser supports it) fills the editable answer box. It **never auto-submits** and typing is always available. **Ask4Mo does not record or store audio** and derives no emotion, accent, confidence or personality signal from the voice. Question playback (text to speech) is optional.
- **Data used:** the setup, the job description text (resolved on the server, never exposed to the browser), and approved evidence only when the candidate chooses to use it (never the raw CV).
- **Data created:** the session, each question, each typed answer, each evaluation and the report.
- **Persistence:** in-progress sessions persist until completed or discarded; completed interviews are saved to History.
- **Privacy boundary:** owner-scoped; Admins cannot read answers.
- **Routes:** `/practice`.

### Stage 9. Feedback, Deep Dive and report
- **Per-answer feedback** shows the **Interview Answer Score** and the criteria (stage 8 scoring below), what worked, what to improve, evidence that was missing, a stronger answer structure and a likely follow-up.
- **Deep Dive:** after an answer the candidate may go deeper on that answer in one of six styles (for example deepen the reasoning or challenge assumptions), for up to two follow-up levels, then **return to the main interview**. A Deep Dive uses the same score presentation and does not change the main interview's progress.
- **Final report:** at the end the candidate generates a report with a **Practice Readiness** score (0 to 100, shown as "Practice readiness"), the performance summary, strengths, development priorities, recurring patterns, highest-risk questions, evidence gaps, recommended practice actions and a final checklist. It is generated once per interview and saved to History; if saving fails the candidate is told and can retry.
- **Difference:** the per-answer score describes **one answer**. Practice Readiness describes the **whole interview session** and is a separate number.
- **Persistence:** the report is saved to History and can be exported (Markdown or JSON) from the History detail page.
- **Limitations:** practice feedback only; not a hiring decision.

#### Scoring semantics (preserved from the P2-03 remediation)
- **Interview Answer Score:** 0 to 100, for **one answer**, produced by the evaluation model and checked only for being in range. It is **not** calculated by the application from the criteria, **not** an arithmetic mean, **not** a weighted deterministic formula, and **not** a prediction of a hiring outcome.
- **Seven criteria**, each 1 to 10: **Relevance**, **Structure & clarity**, **Evidence & examples**, **Role knowledge**, **Problem-solving**, **Communication**, **Credibility & consistency**. They are separate criteria considered in the structured evaluation, not inputs to a formula.
- **Credibility & consistency** looks at how consistent and well supported the submitted text is. It is **not** lie detection or honesty detection and never looks at the voice.
- **Voice does not affect scores.** The evaluation receives text only.
- **Practice feedback only, not a hiring decision.**
- **Architecture:** evaluation is a separate, model-backed service whose output is validated against a schema. It is not an agent specialist and there is no deterministic scoring formula.

### Stage 10. Progress
- **Purpose:** see practice progress over time.
- **What it shows:** from the candidate's **completed** interviews: interviews completed, answers evaluated, average practice score (out of 100), average answer time, the most common improvement area, and the five most recent interviews (each links to its History record). Below it, the candidate's **saved Mo memory**, grouped (priorities, strengths, completed, preferences), with removal and a link to Settings.
- **Resilience:** the two parts load independently; one failing does not hide the other.
- **What it is not:** no hiring probability, no career-success prediction, no benchmark against other candidates or recruiters, and no personality scoring.
- **Routes:** `/progress`.

### Stage 11. History
- **Purpose:** revisit completed work.
- **What it shows:** the candidate's saved interviews (role, number of questions, date), each opening a detail page with the report and export (Markdown or JSON). Deleting an interview is a hard delete that also removes its resumable session and any share grant on it.
- **History is not Mo memory.** History is the record of completed interviews and reports. Mo memory is a separate, small set of facts the candidate **approved** (section 5). Neither writes into the other.
- **Owner-scoped:** a foreign id is "not found".
- **Routes:** `/history`, `/history/[id]`.

### Stage 12. Return journey
- **Purpose:** welcome the candidate back to real, persisted work.
- **Behaviour:** when signed in, the home page assembles four independent reads: the **active Practice session** (with a Continue button and question progress), the **count of completed interviews** (History), **answers evaluated** (Progress) and the **count of saved memories**. It shows chips for History, Progress and saved memory, and always offers Opportunities and "Prepare another role". Each read fails independently without blocking the others.
- **No fabrication:** if there is no active session and every count is zero, the card renders **nothing**. It never invents activity or a streak.
- **Routes:** `/app`.

### Stage 13. Workspaces and sharing
- **Purpose:** collaborate deliberately, never by default.
- **What is implemented:** a candidate can create a Workspace, see Workspaces they belong to, accept or decline an emailed invitation (72-hour, single-use, and only by the account whose own email was invited) and leave a Workspace. Roles are Workspace owner and Workspace member. Only an owner can invite, remove a member, transfer ownership or deactivate (these owner actions exist in the service; see the limitation below).
- **Sharing model:** only the **owner of an item** can share it, only **into a Workspace they belong to**, only for the item types **interview report** and **story**, and only as **view-only**. Ownership never transfers. Nothing is shared unless an explicit grant exists.
- **Revoking:** the owner of a share can revoke it. **Revocation takes effect immediately for future access** (access is re-checked on every read). **Revocation does not recall what someone already saw.** Deleting the shared item, leaving a Workspace (for that person's own shares) or deactivating a Workspace also ends access.
- **Where to manage it:** **Data & Privacy is the canonical place** to see and revoke sharing: `/account/data#sharing`, reached from the "Manage sharing & access" action there and from a link on the Workspaces page. The empty state states that sharing is private by default and that membership alone gives no access to a CV, reports or Story Bank.
- **Membership alone exposes nothing:** a member sees the member list; they do not see anyone's CV, documents, reports, Story Bank, memory or preparation content unless a specific item was shared with them.
- **Limitations (current interface):** the candidate interface currently offers create, list, accept invitation, leave and revoke. It does **not** currently offer a form to invite people, remove members, or a "share this report" action; those capabilities exist in the API but have no candidate control yet (finding D-01). A shared "preparation summary" type is not enabled.
- **Routes:** `/workspaces`, `/account/data#sharing`.

### Stage 14. Support
- **Purpose:** ask a person at Ask4Mo for help.
- **Candidate action:** open a request with a category (for example account and sign-in, Opportunities, Prepare, Practice, documents, AI response, billing, privacy, accessibility, technical, data issue or other), a subject (up to 200 characters) and a message (up to 5000), optionally with a request reference. Reply on the thread until it is closed.
- **What the candidate sees:** the thread of **customer-visible messages** (their own and Ask4Mo Support replies) and a status: New, Received, In progress, Waiting for your reply, Resolved or Closed.
- **Boundary:** Admin **internal notes are never visible to the candidate**; they live in a separate Admin-only table with no candidate code path and are excluded from the data export. Support sees only what the candidate sent to Support plus safe account metadata; CVs, documents, answers and Mo chats are not available to Support.
- **Not provided:** attachments, email notifications and a service-level or response-time promise. The page says there is no email and that no response time can be promised.
- **Failure behaviour:** a failed send is never retried automatically and the text stays in the form.
- **Routes:** `/support`.

### Stage 15. Data & Privacy
- **Purpose:** inspect and control the candidate's data. Route: `/account/data`.
- **What it offers:** an overview (Opportunities, documents, saved memories, practice interviews, items shared, Workspaces, account and preferences); **export** as a single JSON file built on demand; **per-item controls**; **sharing management**; plain-language retention; privacy requests; legal-document acceptance; and **account deletion**. Each section loads on its own with its own retry.
- **Exact verbs used (they are not interchangeable):**
  - **Archive:** hide an Opportunity but keep it.
  - **Delete:** remove an Opportunity, document, saved memory or practice interview. The confirmation says "Delete for good".
  - **Revoke:** end a share grant (access ends for the future; it does not recall what was seen).
  - **Unlink:** deleting an Opportunity unlinks its interviews and reports instead of deleting them.
  - **Anonymise:** security and audit records are kept for the platform with the person's identity removed after account deletion.
- **Export contents:** account and preferences, Opportunities, document metadata and extracted items, stories, memories, interviews, feedback submitted, Workspace memberships and shares, support threads with visible messages, plan history, recorded legal acceptances, privacy requests and a preparation-run index. **Not included:** the original uploaded files, security and audit records, other people's data, internal prompts and secrets, support internal notes and preparation-chat content.
- **Account deletion:** removes the account and its data child-first (including stored files and Mo run state); owned Workspaces transfer to another member or are deleted; security records are kept with identity removed. The confirmation states its limits.
- **Limitations stated to the candidate (and repeated here):** backups are not erased instantly; some preparation-chat working data may remain until cleanup, and a single chat cannot be removed on its own from the page; no fixed retention periods are promised. Ask4Mo does **not** claim to delete everything it knows about a person instantly, and makes no legal-compliance or certification claim.

### Stage 16. Trust and Settings
- **Trust (`/trust`):** explains that Mo is AI and can be wrong, that sources are shown when career evidence is used, that facts are kept apart from opinion and suggestions, that evidence is governed, that agents are bounded, that nothing here is a hiring decision, that data is private by default and sharing is explicit, that no voice-trait inference or audio storage exists, and how to export and delete. It carries no certification badges and makes no compliance claim. `/ai-transparency`, `/privacy` and `/terms` are linked.
- **Settings (`/settings`):** profile (name, target role, career geography, coaching style, with a link back to onboarding), language (interface, Mo conversation and dictation as three independent choices, with a note that none changes the career region), response detail (Brief or Detailed; detail and sources stay behind "Show more"), **saved Mo memory** (edit, pin, delete) and a link to Data & Privacy.
- **Account (`/account`):** email and verification status, sign-in method, plan summary (Basic, or Premium preview with nothing to buy), sign out.

## 5. The memory model
These stores are different and are never interchangeable.

| Category | What it is | Persists? | Candidate control |
|---|---|---|---|
| Conversation / run context | The current Mo conversation and run state | Kept so the run can be resumed; not a long-term profile | Start a new run; account deletion purges it; single chats cannot be removed yet |
| **Approved Mo memory** | A short, selective fact the candidate approved (category, summary up to 500 characters, optional role) | Yes, until deleted | Approve, edit before saving, reject; edit, pin or delete in Settings; deletion in Data & Privacy |
| Interview / history records | Completed interviews and reports | Yes | View, export, delete |
| Documents and evidence | Uploaded files, extracted items, stories | Yes, private | Review, correct, reject, delete |
| Opportunity context | Role, company, optional job description link | Yes | Archive, delete |
| Workspace sharing | View-only grants on selected items | Until revoked or the item is deleted | Revoke in Data & Privacy |

**Mo memory persists only after the candidate approves it.** It never stores whole conversations, job descriptions, CVs, transcripts, answers, retrieved evidence or provider output, and it has no protected-trait categories. Saved memory is loaded as **data**, never as instructions, and never overrides what the candidate says in the current request.

## 6. Provenance in Prepare (how to read a Mo answer)
Four plain labels, introduced in the P2-04 remediation:
- **AI-generated:** Mo created this response with AI. Check important details. Every Mo answer carries it.
- **External sources used:** the career sources retrieved for this preparation, listed with their titles. They support the retrieved evidence; **they do not make Mo's whole answer verified or source-backed**, and Mo's response itself is still AI-generated.
- **Your evidence considered:** shown only when Mo actually selected some of the candidate's own approved evidence in this run. It is not shown merely because a CV exists or an Opportunity is selected.
- **Reviewed by you:** the candidate reviewed that item. It is a statement about the candidate's own review, not third-party verification.

Ask4Mo never claims that an answer is fact-checked, fully verified or that all answers are verified.

## 7. AI architecture: candidate-friendly view
- **Mo** is one stateful, bounded agent with a step budget per turn and human approvals at three points.
- **Three bounded specialists** sit behind Mo (role, candidate evidence, interview strategy). They are advisory and cannot start Practice or save memory.
- **Retrieval** over the career knowledge base is used when it helps; retrieved text is data.
- **Candidate evidence** reaches Mo only if the candidate approved it, and only for that candidate.
- **Evaluation** (Practice scoring and the final report) is a separate model-backed, schema-validated service, not an agent specialist and not a formula.

### Engineering reference (for reviewers)
Registry: `career_tool_registry` in `src/agent/registry.py` (11 tools: 6 career, 3 specialist, 2 human-action). Specialists: `src/agent/specialists/registry.py` (three). Human review: `src/agent/human.py` and the human-review node in `src/agent/nodes.py` (interrupt first, memory persisted only after validated approval). Checkpointing: `src/agent/checkpoint.py` (durable; fail-closed when durability is configured). Practice: `src/session_manager.py`, `src/interview/`, `src/api/routes/interview.py`; scoring models in `src/models.py` (`AnswerEvaluation`, `FinalInterviewReport`). Opportunity: `src/application/opportunity_service.py`. Documents: `src/documents/`, `src/application/documents_service.py`. Sharing: `src/application/sharing_service.py`. Language lists: `src/locales.py` and `frontend/lib/i18n/locales.ts`.

## 8. Voice and language boundaries
Dictation, text-to-speech and realtime voice are three different things and are documented separately.
- **Dictation** (speaking an answer into an editable box): 7 languages (English, German, French, Spanish, Italian, Portuguese, Dutch); Russian excluded; depends on browser support; never auto-submits; the language is a per-device choice.
- **Listen aloud (text to speech):** the same 7 languages, Russian excluded; browser dependent; live human quality is unvalidated. Speech and dictation do not run at the same time, and playback never opens the microphone.
- **Realtime voice:** **off by default**; it needs explicit configuration and a provider credential; same 7 languages; limited session length and one session at a time; live behaviour is **not validated**. It is available only where the deployment has enabled it.
- **Always:** no audio is recorded or stored, and no emotion, accent, confidence, personality, intelligence or honesty signal is derived from voice (CLAIM-009 to CLAIM-011).

## 9. Failure and recovery
- **Empty states** are honest ("Your completed interviews will appear here", "No stories yet", "Nothing shared yet", "You have not contacted support yet") and never fabricate activity.
- **Errors** are proportional and plain: offline, cannot reach the service, session expired, not found, already being processed, too many requests, service unavailable, and a "platform paused" message that says saved data remains available. Retry is offered on sections and pages; technical details are collapsed.
- **Resumable work:** Practice is durable and resumable (and recoverable from an interrupted step); a Prepare run restores from its address and a stale address offers "Start new preparation"; a failed document can be retried or replaced. **Not every workflow is resumable:** for example a failed support send or an unsent form is not saved automatically.
- **Insufficient evidence:** Mo says it does not have enough reliable evidence and suggests adding a job description or more role detail, with no fabricated confidence or score.
- **Provider failures:** surfaced through the generic safe error messages; there is no provider-specific copy yet (finding D-07).

## 10. Navigation reference
| Surface | Route | Class | Purpose |
|---|---|---|---|
| Opportunities | `/opportunities` | Primary | The home for each job |
| Prepare | `/prepare` | Primary | Prepare with Mo |
| Practice | `/practice` | Primary | Realistic interview practice |
| Progress | `/progress` | Primary | Practice progress and saved memory |
| History | `/history` | Primary | Completed interviews and reports |
| Company research | `/company` | Supporting ("More") | Research an employer |
| Documents | `/documents` | Supporting ("More") | Private evidence and Story Bank |
| Workspaces | `/workspaces` | Supporting ("More") | Teams and explicit sharing |
| Sources | `/sources` | Supporting ("More") | Career evidence behind Mo's answers |
| Help | `/help` | Supporting ("More") | How Ask4Mo works |
| Account | `/account` | Account menu | Email, plan, sign out |
| Settings | `/settings` | Account menu | Preferences, languages, memory |
| Data & Privacy | `/account/data` | Account menu | Export, delete, sharing, requests |
| Trust & AI use | `/trust` | Account menu | AI limits and data boundaries |
| Support | `/support` | Supporting (linked from Help) | Contact Ask4Mo |

Review & Diagnostics and Admin are shown in "More" only to a server-authorised Admin; they are not part of the candidate journey.

## 11. Data lifecycle
| Data | Created where | Used where | Persists? | Candidate controls | Sharing | Deletion / revocation |
|---|---|---|---|---|---|---|
| Opportunity | Opportunities | Company research, Prepare, Practice | Yes | Edit status, archive, delete | Never shared by default | Delete unlinks interviews and reports; they remain in History |
| Document | Documents | Evidence, job-description picker | Yes, private | Download, retry, replace, delete | Not shareable | Delete removes file, text and items; stories lose their source |
| Extracted item | Documents | Story Bank; Mo only after approval | Yes | Accept, correct, reject | Not shareable | Removed with the document |
| Story | Documents (Story Bank) | Practice and Prepare (approved) | Yes | Create, edit, delete | Shareable view-only (API) | Revoke; source deletion cuts access |
| Mo memory | Prepare (approved) or Settings | Loaded as data in Prepare runs | Yes, until deleted | Approve, edit, pin, delete | Never shared | Delete in Settings or Data & Privacy |
| Practice session | Practice | Practice, Return card | Until completed or discarded | Resume, discard | Not shared | Discard or delete |
| Evaluation and report | Practice | History, Progress | Yes | View, export, delete | Report shareable view-only (API) | Delete removes it and any share |
| Workspace share | Sharing (API) | Workspaces | Until revoked | Revoke in Data & Privacy | The share itself | Revoke ends future access |
| Support message | Support | Support thread | Yes | Reply | Visible to Support | Deleted with the account |

No retention period is promised for any of these; items are kept until the candidate deletes them or deletes the account.

## 12. Trust boundaries
| Candidate assumption | Actual Ask4Mo behaviour |
|---|---|
| "Mo is a recruiter or a person" | No. Mo is AI and can make mistakes. Ask4Mo does not make hiring decisions. |
| "Ask4Mo can tell me whether I will get the job" | No. Scores are practice feedback, not a hiring decision or a prediction. |
| "A reviewed item was independently verified" | No. It was reviewed by the candidate ("Reviewed by you"). |
| "A source badge verifies the whole answer" | No. Sources support retrieved evidence only; Mo's wording is still AI-generated. |
| "The overall score is the average of the seven criteria" | No. It is produced by the evaluation model; the criteria are separate. |
| "Credibility means it can tell if I am lying" | No. It judges the consistency and support of the submitted text only. |
| "My voice changes my score" | No. Scoring uses text only and no audio is stored. |
| "Joining a Workspace exposes my preparation" | No. Sharing is explicit, per item, and view-only. |
| "Revoking a share unsees it" | No. Revocation ends future access; it does not recall what was seen. |
| "Deleting an Opportunity deletes my interview history" | No. Interviews and reports remain in History, unlinked. |
| "A Russian interface means the Russian labour market" | No. Language never sets the geography, and Russia is not a supported market. |
| "Russian works for voice, documents and the knowledge base" | No. Russian is the interface and conversation only. |
| "Deleting my account removes everything instantly" | No. Backups are not erased instantly and some chat working data may remain until cleanup. |
| "Admins can read my CV or chats" | No. Admins see account metadata only. |
| "Company research covers Glassdoor or LinkedIn" | No. Those are not integrated. |

## 13. Product-claim discipline
Every externally meaningful sentence above was checked against `PRODUCT_CLAIMS.md`. The positioning sentence, the value proposition and the trust statement are used as written. None of the prohibited claims is made: no compliance or certification claim, no "100% secure" or "completely private", no "bias-free", no "fully verified" or "all answers verified", no "human reviewed", no outcome guarantee, no comparison with other products or human coaching, no employer or recruiter positioning, no testimonial or customer count, no unsupported Russian claim and no live-billing claim.

## 14. Known limitations that apply to this journey
Premium is a preview (nothing to buy); Google sign-in is not available to candidates and not validated live; sign-in does not require a verified email; rate limiting is in memory per process; OCR live quality is unvalidated and the Russian language is not supported for documents; realtime and text-to-speech live quality are unvalidated; the Russian interface is an engineering translation pending native and legal review; live Mo answer quality is not measured by the deterministic tests; backups are not erased instantly and single preparation chats cannot be removed individually; no retention periods are promised.

## 15. Human validation status
The Pilot 2 findings P2-01 (sharing discoverability), P2-02 (isolated knowledge environment), P2-03 (score interpretation) and P2-04 (provenance clarity) are REMEDIATED and qualified by deterministic tests, and are **pending human revalidation**. The Pilot 2 historical verdict on RC-P10-003 (CONDITIONAL GO, targeted remediation required) is unchanged. AC-24 remains PARTIAL. RC-P10-004 has not been created.

## 16. Test and evaluator anchors
Primary navigation and routes: `frontend/components/layout/nav-items.ts`. Deterministic gates that protect statements in this document: `eval_opportunity_journey`, `eval_documents_evidence`, `eval_multi_agent`, `eval_agent`, `eval_workspace_security`, `eval_privacy_controls`, `eval_voice_experience`, `eval_i18n_l10n`, `eval_product_positioning` and `eval_doc_consistency`; Playwright specs for the journey, Opportunities, documents, agent coach, interview, data privacy, workspaces, support and the Russian locale.

## 17. Documentation findings (recorded, not fixed here)
These are differences between current behaviour and other wording or an expectation. They are recorded for the owner and are not product changes in this wave.
| ID | Finding | Severity |
|---|---|---|
| D-01 | The candidate interface has no control to invite members or to share a report or story (create, list, accept invitation, leave and revoke exist). CLAIM-017 ("share selected items") is therefore only partly reachable by a candidate today. | MEDIUM |
| D-02 | The pricing page presents Premium as a EUR 19.99 per month plan to choose, while the account page says Premium is a preview with nothing to buy. | MEDIUM |
| D-03 | Data export copy still carries stale legal-acceptance wording ("not recorded yet", and a `recorded: false` entry) although acceptance recording now exists. | LOW |
| D-04 | `PRODUCT_CLAIMS.md` has stale entries: NO-05 and NO-06 reference issues since closed in W10.10, and NO-16 says ticketing is not built although ticketing exists (SLA, email and attachments are absent). | LOW |
| D-05 | The "Reviewed by you" provenance kind is defined but not rendered as a Prepare badge, and no interface path creates an "AI suggested" story. | LOW |
| D-06 | Opportunity fields other than status cannot be edited in the interface after creation. | LOW |
| D-07 | There is no provider-specific failure copy; failures use generic safe messages. | LOW |
| D-08 | The dictation language is a per-device setting and does not follow the account across devices. | LOW |

These findings are not fixed in this wave. The Platform Admin journey and specialist Admin journeys are separate documents and are not part of this one.
