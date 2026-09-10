import { HomeEntry } from "@/components/coach/HomeEntry";

export default function HomePage() {
  return (
    <section className="animate-enter">
      <div className="grid max-w-3xl gap-5 py-8 md:py-12">
        <div>
          <p className="text-2xl font-bold tracking-tight text-accent">Ask4Mo</p>
          <p className="text-sm font-semibold text-muted">Intelligent Interview Coach</p>
        </div>
        <h1 className="text-4xl font-semibold tracking-tight md:text-5xl lg:text-6xl">
          Prepare for the interview that matters.
        </h1>
        <p className="text-lg font-semibold text-foreground">Ask More. Be More.</p>
        <p className="max-w-reading text-lg text-muted">
          Tell Mo what you&rsquo;re preparing for. Get a focused plan, evidence when
          needed, and a clear path into practice.
        </p>
        <HomeEntry />
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {[
            ["Prepare with evidence", "Grounded career information and citations when needed."],
            ["Practise with purpose", "Tailored questions based on the role and your preparation context."],
            ["Stay in control", "Memory and important handoffs require clear approval."],
            ["Improve over time", "Structured feedback, progress and reusable preparation context."],
          ].map(([title, body]) => (
            <div key={title}>
              <p className="text-sm font-semibold text-foreground">{title}</p>
              <p className="text-sm text-muted">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
