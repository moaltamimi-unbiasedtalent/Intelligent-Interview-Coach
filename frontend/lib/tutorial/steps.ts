/**
 * Guided-tour definition. Route-aware, ~12 steps across the real product journey.
 * Each step targets a stable `data-tour` attribute where one reliably exists; steps
 * that would need generated data (a live handoff card, an in-progress answer, a report)
 * fall back to a route-level explanation with no highlight — never fabricated state.
 */

/** Bump when the tour changes materially so a completed user can be re-invited. */
export const ASK4MO_TUTORIAL_VERSION = 1;

export interface TutorialStep {
  id: string;
  route: string;
  /** data-tour value to highlight, if present on the route. Omit/absent → card only. */
  target?: string;
  title: string;
  body: string;
  /** Help Center anchor for "Learn more" (reuses existing articles; no duplicate copy). */
  helpHref?: string;
}

export const TUTORIAL_STEPS: TutorialStep[] = [
  {
    id: "home-start", route: "/app", target: "home-start",
    title: "Start with your goal",
    body: "Ask4Mo helps you prepare for a target role, practise realistic interview questions and track improvement.",
    helpHref: "/help#getting-started",
  },
  {
    id: "target-role", route: "/prepare", target: "target-role",
    title: "Give Mo the right context",
    body: "Add your target role and, when available, the job description. Better context produces more relevant preparation.",
    helpHref: "/help#prepare",
  },
  {
    id: "ask-mo", route: "/prepare", target: "ask-mo",
    title: "Prepare with your AI Coach",
    body: "Mo can analyse the role, identify gaps, build a preparation plan and choose bounded tools when they are useful.",
    helpHref: "/help#prepare",
  },
  {
    id: "sources", route: "/sources", target: "sources",
    title: "See the evidence",
    body: "When factual evidence is needed, Mo can use governed Career Intelligence and show its sources. If reliable evidence is unavailable, Ask4Mo says so rather than inventing a citation.",
    helpHref: "/help#sources",
  },
  {
    id: "memory", route: "/progress", target: "memory",
    title: "You control what Mo remembers",
    body: "Long-term preparation facts require your approval before they are saved. You can edit, pin or delete them in Settings.",
    helpHref: "/help#memory",
  },
  {
    id: "practice-handoff", route: "/prepare", target: "practice-handoff",
    title: "Turn preparation into practice",
    body: "Approved role and focus information can be transferred into Interview Practice through a controlled handoff.",
    helpHref: "/help#practice",
  },
  {
    id: "practice-answer", route: "/practice", target: "practice-answer",
    title: "Practise realistically",
    body: "Answer interview questions and receive structured feedback on each answer.",
    helpHref: "/help#practice",
  },
  {
    id: "deep-dive", route: "/practice", target: "deep-dive",
    title: "Explore feedback",
    body: "Deep Dive lets you investigate a specific answer or evaluation in more detail.",
    helpHref: "/help#practice",
  },
  {
    id: "report", route: "/practice", target: "report",
    title: "Review your performance",
    body: "Completed practice produces an overall report with strengths and areas to improve.",
    helpHref: "/help#practice",
  },
  {
    id: "progress", route: "/progress", target: "progress",
    title: "Track improvement",
    body: "Progress uses your completed Practice data to show activity, performance and focus areas.",
    helpHref: "/help#progress",
  },
  {
    id: "history", route: "/history", target: "history",
    title: "Return to previous interviews",
    body: "History lets you reopen completed interview sessions and their reports.",
    helpHref: "/help#history",
  },
  {
    id: "help", route: "/help", target: "help",
    title: "Help is always available",
    body: "Replay this tour or search the Help Center whenever you need guidance.",
    helpHref: "/help",
  },
];
