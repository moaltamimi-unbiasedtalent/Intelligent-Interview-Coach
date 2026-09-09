import { HomeEntry } from "@/components/coach/HomeEntry";

export default function HomePage() {
  return (
    <section className="animate-enter">
      <div className="grid max-w-3xl gap-5 py-8 md:py-12">
        <p className="text-sm font-semibold text-accent">Interview preparation, guided</p>
        <h1 className="text-4xl font-semibold tracking-tight md:text-5xl lg:text-6xl">
          Prepare for the interview that matters.
        </h1>
        <p className="max-w-reading text-lg text-muted">
          Tell the coach what you&rsquo;re preparing for. It maps what the role needs,
          where you&rsquo;re strong, and what to practise &mdash; then helps you rehearse.
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
