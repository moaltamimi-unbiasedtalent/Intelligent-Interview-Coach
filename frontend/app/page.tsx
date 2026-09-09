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
          Tell Mo what you&rsquo;re preparing for and build a focused plan for the
          interview ahead &mdash; grounded in evidence, then practised with purpose.
        </p>
        <HomeEntry />
        <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
          <span>◦ Evidence-grounded guidance</span>
          <span>◦ Realistic interview practice</span>
          <span>◦ Calm, focused, private</span>
        </div>
      </div>
    </section>
  );
}
