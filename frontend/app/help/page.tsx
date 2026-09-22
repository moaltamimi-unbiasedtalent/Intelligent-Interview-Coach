import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";

export const metadata: Metadata = { title: "Help" };

const SURFACES: Array<{ title: string; body: string }> = [
  { title: "Ask Mo", body: "Tell Mo the interview you're preparing for. Mo is your AI coach — it plans your preparation and pulls in evidence when it helps. You stay in control of what happens next." },
  { title: "Prepare", body: "Mo analyses the role/job description, compares your background, highlights priority gaps, and drafts tailored questions. It retrieves grounded career evidence when useful, and only remembers something when you approve it." },
  { title: "Practise", body: "Approved preparation hands off into a realistic interview: a question at a time, structured feedback on each answer, an optional Deep Dive to go further, then a final performance review. Feedback is practice guidance, never a hiring decision." },
  { title: "Progress", body: "Your practice progress — sessions completed, answers evaluated, average practice score and your most common focus area — alongside the preparation memory you've chosen to save." },
  { title: "History", body: "Every completed interview and its report, kept private to you. Open any session to re-read its full performance review." },
  { title: "Sources", body: "The governed, public career evidence behind your preparation. Where an official public record exists, the source links out so you can verify it yourself." },
  { title: "Review & Diagnostics", body: "For reviewers: the Agent Inspector shows a run's safe tool/retrieval/HITL activity (open it from a run's “View run details”, or paste a run ID); Knowledge & RAG shows governed counts and offline retrieval quality; Evaluation shows offline RAGAS metrics. No chain-of-thought, prompts or secrets are ever shown." },
];

const CONCEPTS: Array<{ title: string; body: string }> = [
  { title: "Mo is an AI coach, not an autonomous decision-maker", body: "Mo suggests and prepares; you decide. It never sends messages, makes hiring judgements, or acts irreversibly on your behalf." },
  { title: "Human-in-the-loop (HITL)", body: "The important steps pause for you: confirming an ambiguous role, saving a memory, and handing off to practice. Nothing is saved or started without your approval." },
  { title: "Memory approval", body: "Mo only remembers a preparation fact when you explicitly approve it. You can edit, pin or delete saved memory in Settings, and see it in Progress." },
  { title: "Governed sources", body: "Career evidence comes from a curated, governed knowledge base (official taxonomies, statistics and frameworks) — not open web opinions. Citations point back to public records where they exist." },
  { title: "Current-market research", body: "When a question genuinely needs current information, Mo can use bounded current-market research (advertised roles and an explicit public company page). It never sends your personal data out, and it's off unless enabled." },
];

export default function HelpPage() {
  return (
    <section>
      <PageHeader
        eyebrow="How Ask4Mo works"
        title="Help"
        description="A quick guide to each part of Ask4Mo and the ideas behind it."
      />

      <h2 className="mb-3 text-sm font-semibold text-foreground">The journey</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {SURFACES.map((s) => (
          <Card key={s.title}>
            <CardBody>
              <h3 className="text-base font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-muted">{s.body}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold text-foreground">Good to know</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {CONCEPTS.map((c) => (
          <Card key={c.title}>
            <CardBody>
              <h3 className="text-base font-semibold">{c.title}</h3>
              <p className="mt-1 text-sm text-muted">{c.body}</p>
            </CardBody>
          </Card>
        ))}
      </div>
    </section>
  );
}
