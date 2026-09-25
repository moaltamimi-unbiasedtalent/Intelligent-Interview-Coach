"use client";

import { useMemo, useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { TutorialLauncher } from "@/components/tutorial/TutorialLauncher";

interface Article {
  q: string;
  a: string;
}
interface Section {
  id: string;
  title: string;
  articles: Article[];
}

/** The permanent Help Center content. Deterministic docs — no LLM, no embeddings. */
const SECTIONS: Section[] = [
  {
    id: "getting-started",
    title: "Getting started",
    articles: [
      { q: "What is Ask4Mo?", a: "An AI interview coach. Mo is a bounded AI agent that helps you understand a role, prepare with evidence, practise realistic questions, and track improvement." },
      { q: "How the journey works", a: "Home → Ask Mo → Prepare → Practise → Progress/History. Evidence and human approval run throughout; you stay in control." },
      { q: "Continuing where you left off", a: "When you return, Home shows a “Welcome back” card built from your real activity — resume an in-progress interview, or jump to your latest report, Progress or History. It only appears once you have activity." },
      { q: "Taking the guided tour", a: "Use “Take the tour” below (or on first visit) for a 2-minute route-aware walkthrough. You can replay it any time." },
    ],
  },
  {
    id: "prepare",
    title: "Prepare",
    articles: [
      { q: "Role context", a: "Tell Mo the target role. More context yields more relevant preparation; nothing is required beyond a goal." },
      { q: "Job descriptions", a: "Paste a JD when you have one — Mo analyses requirements and compares them to your background." },
      { q: "Asking Mo", a: "Mo decides whether to retrieve evidence and which bounded tools to use. It suggests; you decide." },
      { q: "Preparation plans", a: "Mo builds a focused plan and tailored questions from the role and your gaps." },
      { q: "Brief or Detailed answers", a: "In Settings, choose Response detail: Brief leads with the key answer and next step; Detailed shows the fuller explanation inline. This is presentation only — it never changes what Mo works out, and it is separate from the Fast/Balanced/Advanced model speed." },
      { q: "“Show more” and sources", a: "In Brief mode, supporting detail sits behind a “Show more” control and sources stay in their own expandable list — nothing is removed, only tucked away until you want it. Important qualifications always stay visible." },
    ],
  },
  {
    id: "practice",
    title: "Practice",
    articles: [
      { q: "Starting Practice", a: "Approve the handoff from Prepare, or start Practice standalone. A session runs one question at a time." },
      { q: "Evaluations", a: "Each answer gets structured feedback — strengths, improvements and evidence gaps. It is practice guidance, not a hiring decision." },
      { q: "Deep Dive", a: "Deep Dive lets you investigate a specific answer or evaluation in more detail, then return to the interview." },
      { q: "Reports", a: "Completing a session produces a performance review with an overall readiness score, strengths and priorities." },
    ],
  },
  {
    id: "progress",
    title: "Progress",
    articles: [
      { q: "What the metrics mean", a: "Sessions completed, answers evaluated, average practice score and your most common focus area — derived only from your completed practice." },
      { q: "Why Progress may be empty", a: "Progress fills in after your first completed practice session. Saved preparation memory also appears here once you approve it." },
    ],
  },
  {
    id: "history",
    title: "History",
    articles: [
      { q: "What gets stored", a: "Your completed interview sessions and their reports, private to you." },
      { q: "When a report appears", a: "After a session is completed and its report generated. In-progress sessions are not listed as history." },
      { q: "How to reopen a session", a: "Open any row in History to re-read its full performance review." },
      { q: "Resuming an in-progress interview", a: "An interview you haven’t finished isn’t in History — it’s resumable from the “Welcome back” card on Home. Completed interviews live in History; in-progress ones you continue." },
    ],
  },
  {
    id: "sources",
    title: "Sources",
    articles: [
      { q: "Governed Career Intelligence", a: "Evidence comes from a curated, governed knowledge base (official taxonomies, statistics and frameworks) — not open-web opinions." },
      { q: "Public source links", a: "Where an official public record exists, a source links out so you can verify it yourself (opens safely in a new tab)." },
      { q: "Knowledge-index readiness", a: "The Knowledge & RAG page shows governed counts and offline retrieval quality. Some deployments show the source catalogue before the local index is built." },
      { q: "Current-market evidence", a: "Bounded current-market research (advertised roles and an explicit public company page) can supplement governed knowledge; it is off unless enabled and never sends your data out." },
      { q: "Why evidence may be unavailable", a: "If reliable evidence is not available for a query, Mo says so rather than inventing a citation." },
    ],
  },
  {
    id: "dictation",
    title: "Using dictation",
    articles: [
      { q: "Where dictation is available", a: "Where your browser supports speech recognition, a microphone button appears next to text inputs on Prepare (talking to Mo) and in Interview Practice (your answer). If it isn't shown, your browser doesn't support it — you can always type." },
      { q: "How to start and stop", a: "Click the microphone to start; the button shows a listening state. Click it again (or use the keyboard) to stop. Speech is transcribed into the normal text box." },
      { q: "Editing and sending", a: "Recognised speech is added to the editable field so you can read and edit it first. Dictation never sends anything on its own — you always press Send or Submit yourself." },
      { q: "Choosing a dictation language", a: "A small selector offers Ask4Mo's supported dictation languages: English, German, French, Spanish, Italian, Portuguese and Dutch. This sets the speech-recognition language only — it does not translate your words and does not change the app's language." },
      { q: "Which languages actually work", a: "The languages above are configured and offered, but which ones your device can actually transcribe is browser- and engine-dependent. If a language isn't recognised well in your browser, type instead or try another supported browser." },
      { q: "Browser compatibility", a: "Dictation uses your browser's built-in speech recognition (best supported in Chrome-based browsers). Where it isn't available, the microphone simply isn't shown and typing works as normal." },
      { q: "Microphone permission", a: "Your browser asks for microphone permission the first time. If you decline, dictation won't run and Ask4Mo shows a short note — you can still type. You can re-enable the microphone in your browser's site settings." },
      { q: "Privacy", a: "Ask4Mo does not analyse your emotions, voice characteristics, or identity. It does not record or store audio. Only the text you explicitly submit is sent — exactly like typing. Note that browser speech recognition may send audio to your browser/vendor's speech service to produce the transcript; that processing is your browser's, not Ask4Mo's." },
    ],
  },
  {
    id: "voice",
    title: "Voice: listening & speaking",
    articles: [
      { q: "Listen to Mo or a question", a: "Where your browser supports speech synthesis, a Listen button lets you hear Mo's response or an Interview Practice question read aloud. Playback never starts on its own — you press Listen, and you can press Stop any time." },
      { q: "Speak an answer", a: "Use the microphone (dictation) to speak your answer or message. Your words appear as an editable transcript; you review and edit them, then press Send or Submit yourself. Speaking never submits automatically, and Listen never opens the microphone for you." },
      { q: "Languages", a: "Voice playback maps your Mo conversation language to a bounded speech voice (English, German, French, Spanish, Italian, Portuguese, Dutch). Whether a suitable voice is installed is browser/OS-dependent; if none is available, the text stays on screen to read. Your interface language, dictation language and Mo conversation language remain separate settings, and a voice language never changes career/salary geography." },
      { q: "Sources when listening", a: "Long links aren't read aloud. When a response cites sources, playback says the sources are available on screen — the source links stay visible and inspectable in the normal view." },
      { q: "Privacy & what voice is NOT used for", a: "Ask4Mo hands the visible text to your browser/OS speech engine and stores no synthesised audio. Ask4Mo never uses your voice to infer emotions, personality, intelligence, honesty, deception, accent quality or hiring suitability — voice is only a way to listen and to enter text. There is no voice score of any kind." },
      { q: "If voice isn't available", a: "If your browser has no speech synthesis or no installed voice, the Listen button simply doesn't appear and you read the text normally. Voice never blocks any feature." },
    ],
  },
  {
    id: "documents",
    title: "Documents & evidence",
    articles: [
      { q: "Uploading documents", a: "On the Documents page you can privately upload a CV, a job description, a portfolio or a brief. Files are private to you — never shared, never added to public knowledge." },
      { q: "Supported formats", a: "PDF, DOCX and TXT (up to 10 MB). Scanned PDFs and images (PNG/JPEG) are read with OCR where your deployment supports it." },
      { q: "OCR (scanned files)", a: "When a file has no selectable text, Ask4Mo uses optical character recognition to read it. OCR text is labelled as OCR-derived and its quality depends on the scan and the browser/engine." },
      { q: "Why a file can't be read", a: "Password-protected, corrupt, empty or unsupported files can't be processed — you'll see a clear status and can upload a different file. Typing is never blocked." },
      { q: "Reviewing extracted facts", a: "Ask4Mo extracts evidence with a link back to the page/section it came from. Nothing becomes reusable until you accept it — you can accept, correct or reject each item." },
      { q: "Correcting extraction", a: "Editing an item marks it as your correction; the original extracted text is kept for provenance. Ask4Mo never invents facts." },
      { q: "Evidence provenance", a: "Every claim shows its source document and location. Model inference, current-market evidence and your private documents are kept distinct." },
      { q: "Story bank", a: "Turn approved evidence into reusable interview stories. A story built from your evidence is “source-backed”; one you write yourself is “your own”." },
      { q: "Verified vs suggested stories", a: "A source-backed story stays “evidence verified” only while its supporting evidence exists. Editing it marks it “you corrected”. Ask4Mo never fabricates numbers or outcomes." },
      { q: "Replacing a CV", a: "Uploading a new version keeps the old version for provenance so earlier outputs still know which version they used." },
      { q: "Deleting documents", a: "Deleting a document removes the file, its extracted text and claims immediately. Stories that relied on it lose their source and are marked “source removed”." },
      { q: "Exporting reports", a: "From a completed interview in History you can export the report as Markdown or JSON. Export uses the stored report only and never includes internal system data." },
      { q: "Privacy", a: "Your documents are private, never public knowledge, and never analysed for identity or emotion. This is content validation, not malware scanning; a production deployment adds a scanner." },
    ],
  },
  {
    id: "memory",
    title: "Memory & approvals",
    articles: [
      { q: "Approval", a: "Long-term preparation facts are saved only when you approve them. Mo never silently turns your conversation into memory." },
      { q: "Edit, pin, delete", a: "Manage saved memory in Settings — edit wording, pin priorities, or delete anything." },
      { q: "What Mo does not automatically save", a: "Whole conversations, CVs, job descriptions, answers, reports and retrieved evidence are never auto-saved as memory." },
    ],
  },
  {
    id: "privacy",
    title: "Privacy & safety",
    articles: [
      { q: "User scoping", a: "Your sessions, history, progress and memory are private to your account; one user can never read another's data." },
      { q: "Human approval", a: "The decisions that matter — ambiguous role, saving memory, practice handoff — pause for your approval." },
      { q: "External research boundaries", a: "Current-market research is bounded (specific providers, SSRF-safe, no arbitrary browsing) and never sends candidate data outward." },
      { q: "AI limitations", a: "Mo can be wrong or lack evidence; scores are practice guidance, not a hiring decision, and Mo declines to fabricate sources." },
    ],
  },
  {
    id: "troubleshooting",
    title: "Troubleshooting",
    articles: [
      { q: "No progress yet", a: "Complete a practice session — Progress is derived from completed practice." },
      { q: "No history yet", a: "History lists completed sessions with reports; finish a session to see it." },
      { q: "No sources shown", a: "Sources appear when preparation uses governed evidence; some queries need none." },
      { q: "Knowledge index not ready", a: "The governed source catalogue is available even before the local vector index is built; see Knowledge & RAG." },
      { q: "Incomplete Practice", a: "You can resume an in-progress session; a report appears once the session is completed." },
      { q: "Report unavailable", a: "Generate the performance review at the end of a session; reopen it later from History." },
      { q: "Cannot find an Inspector run", a: "Open the Agent Inspector from a Coach run's “View run details”, or paste the run ID. There is no run browser." },
      { q: "A request failed", a: "Retry; if it persists, the error card shows a request id you can quote. No internal details are exposed." },
    ],
  },
  {
    id: "reviewer",
    title: "Reviewer & technical guide",
    articles: [
      { q: "Agent Inspector", a: "Safe per-run traces: tools, retrieval, HITL, model/profile, tokens, latency — never chain-of-thought, prompts, checkpoints or secrets." },
      { q: "Knowledge & RAG", a: "Governed runtime counts + offline deterministic retrieval-quality metrics and known gaps (read-only)." },
      { q: "Evaluation", a: "The latest offline RAGAS run, read-only. It never triggers a paid evaluation and is not live candidate analytics." },
      { q: "Model profiles", a: "Fast / Balanced / Advanced select the model tier only; tools, grounding, memory, HITL and security are identical across tiers." },
      { q: "Tool activity & HITL events", a: "The Inspector timeline shows tool requests/results and human-approval events as safe metadata." },
    ],
  },
];

export function HelpCenter() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return SECTIONS;
    return SECTIONS.map((s) => ({
      ...s,
      articles: s.articles.filter(
        (a) =>
          s.title.toLowerCase().includes(q) ||
          a.q.toLowerCase().includes(q) ||
          a.a.toLowerCase().includes(q),
      ),
    })).filter((s) => s.articles.length > 0);
  }, [query]);

  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold">New here?</h2>
            <p className="text-sm text-muted">Take a 2-minute guided tour of the whole journey.</p>
          </div>
          <TutorialLauncher />
        </CardBody>
      </Card>

      <div>
        <label htmlFor="help-search" className="sr-only">Search help</label>
        <Input
          id="help-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search help — e.g. progress, sources, memory, report"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-muted">No help topics match “{query}”. Try a different word.</p>
      ) : (
        filtered.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-24">
            <h2 className="mb-2 text-sm font-semibold text-foreground">{s.title}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {s.articles.map((a) => (
                <Card key={a.q}>
                  <CardBody>
                    <h3 className="text-sm font-semibold">{a.q}</h3>
                    <p className="mt-1 text-sm text-muted">{a.a}</p>
                  </CardBody>
                </Card>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
