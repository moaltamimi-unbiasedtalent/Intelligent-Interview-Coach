"use client";

import Image from "next/image";
import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { CandidateStory } from "@/components/marketing/CandidateStory";
import { WorkflowMap } from "@/components/marketing/WorkflowMap";
import { cn } from "@/lib/utils";

// v4 Getting Started: short hero, static candidate story, interactive workflow map, six visual steps, a first-15-minutes
// checklist and links to Trust and AI transparency. Imagery: editorial illustrations explain the system; the
// candidate story is a fictional, AI-generated still sequence (no video, no testimonial).

const STEPS: { n: number; visual?: "opportunity" | "sources" | "conversation"; image?: { src: string; altKey: string; w: number; h: number } }[] = [
  { n: 1, visual: "opportunity" },
  { n: 2, visual: "sources" },
  { n: 3, image: { src: "/images/ask4mo/ask4mo-v4-trust-evidence-editorial.png", altKey: "gettingStarted.step3Alt", w: 1536, h: 1024 } },
  { n: 4, visual: "conversation" },
  { n: 5, image: { src: "/images/ask4mo/ask4mo-v4-practice-loop-editorial.png", altKey: "gettingStarted.step5Alt", w: 1672, h: 941 } },
  { n: 6, image: { src: "/images/ask4mo/ask4mo-v4-confidence-practice-editorial.png", altKey: "gettingStarted.step6Alt", w: 1254, h: 1254 } },
];
const CHECKS = [1, 2, 3, 4, 5, 6] as const;

export function GettingStartedContent() {
  const t = useT();
  return (
    <div>
      <section className="mx-auto max-w-content px-4 py-14 text-center md:py-20">
        <p className="text-sm font-semibold uppercase tracking-wide text-accent">{t("gettingStarted.eyebrow")}</p>
        <h1 className="mx-auto mt-3 max-w-3xl text-3xl font-bold tracking-tight md:text-5xl">{t("gettingStarted.title")}</h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">{t("gettingStarted.lead")}</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <ButtonLink href="/register">{t("gettingStarted.ctaPrimary")}</ButtonLink>
          <Link href="/product" className="text-sm font-medium text-foreground hover:underline">{t("gettingStarted.ctaSecondary")} &rarr;</Link>
        </div>
      </section>

      <section id="story" className="border-y border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-14">
          <h2 className="text-2xl font-bold md:text-3xl">{t("gettingStarted.storyTitle")}</h2>
          <p className="mt-3 max-w-2xl text-muted">{t("gettingStarted.storyLead")}</p>
          <div className="mt-8"><CandidateStory /></div>
          <p className="mt-4 max-w-2xl text-sm text-muted">{t("gettingStarted.savedHistoryNote")}</p>
        </div>
      </section>

      <section id="workflow" className="mx-auto max-w-content px-4 py-14">
        <h2 className="text-2xl font-bold md:text-3xl">{t("gettingStarted.workflowTitle")}</h2>
        <p className="mt-3 max-w-2xl text-muted">{t("gettingStarted.workflowLead")}</p>
        <div className="mt-8"><WorkflowMap /></div>
      </section>

      <section id="steps" className="border-t border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-14">
          <h2 className="text-2xl font-bold md:text-3xl">{t("gettingStarted.stepsTitle")}</h2>
          <ol className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {STEPS.map(({ n, visual, image }) => (
              <li key={n} className="group flex flex-col overflow-hidden rounded-[1.25rem] border border-border bg-surface shadow-sm">
                {image ? (
                  <Image src={image.src} alt={t(image.altKey)} width={image.w} height={image.h} sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 380px" loading="eager" className="h-44 w-full object-cover transition-transform duration-500 group-hover:scale-[1.02] motion-reduce:transition-none" />
                ) : visual ? <StepDiagram kind={visual} /> : null}
                <div className="p-5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-foreground" aria-hidden="true">{n}</div>
                  <h3 className="mt-3 font-semibold">{t(`gettingStarted.step${n}Title`)}</h3>
                  <p className="mt-1 text-sm text-muted">{t(`gettingStarted.step${n}Body`)}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="first-15" className="mx-auto max-w-content px-4 py-14">
        <h2 className="text-2xl font-bold md:text-3xl">{t("gettingStarted.checklistTitle")}</h2>
        <p className="mt-3 max-w-2xl text-muted">{t("gettingStarted.checklistLead")}</p>
        <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {CHECKS.map((n) => (
            <li key={n} className="flex items-start gap-3 rounded-lg border border-border bg-surface p-4 text-sm">
              <span aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 rounded border border-border" />
              <span>{t(`gettingStarted.check${n}`)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-t border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-12">
          <h2 className="text-xl font-bold">{t("gettingStarted.linksTitle")}</h2>
          <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold text-accent">
            <li><Link href="/trust" className="hover:underline">{t("gettingStarted.linkTrust")}</Link></li>
            <li><Link href="/ai-transparency" className="hover:underline">{t("gettingStarted.linkAi")}</Link></li>
          </ul>
          <div className="mt-8"><ButtonLink href="/register">{t("gettingStarted.ctaPrimary")}</ButtonLink></div>
        </div>
      </section>
    </div>
  );
}

/**
 * Simple labelled interface diagrams for the steps that have no photograph. They use theme tokens (light and dark),
 * real translated labels and the word "Example", so they explain the product instead of decorating it.
 */
function StepDiagram({ kind }: { kind: "opportunity" | "sources" | "conversation" }) {
  const t = useT();
  const chip = "rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] font-semibold text-foreground";
  const bar = "block h-2 rounded-full bg-border";
  return (
    <div className="relative flex h-44 items-center justify-center overflow-hidden bg-surface-2 p-5" aria-hidden="true" data-testid={`step-diagram-${kind}`}>
      <span className="absolute right-3 top-3 rounded-full bg-surface px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">{t("gettingStarted.exampleLabel")}</span>
      {kind === "opportunity" ? (
        <div className="w-full max-w-[15rem] rounded-xl border border-border bg-surface p-4 shadow-sm">
          <p className="text-sm font-semibold text-foreground">{t("workflow.opportunityTitle")}</p>
          <span className={cn(bar, "mt-3 w-3/4")} />
          <span className={cn(bar, "mt-2 w-1/2")} />
          <div className="mt-4 flex flex-wrap gap-1.5">
            <span className={chip}>{t("journeyCues.stageContext")}</span>
            <span className={chip}>{t("journeyCues.stageEvidence")}</span>
            <span className={chip}>{t("journeyCues.stagePractice")}</span>
          </div>
        </div>
      ) : kind === "sources" ? (
        <div className="flex w-full max-w-[17rem] items-center gap-3">
          <div className="w-1/2 rounded-lg border border-border bg-surface p-3 shadow-sm">
            <span className={cn(bar, "w-3/4")} /><span className={cn(bar, "mt-2 w-full")} /><span className={cn(bar, "mt-2 w-2/3")} /><span className={cn(bar, "mt-2 w-5/6")} />
          </div>
          <span className="text-accent">&rarr;</span>
          <div className="w-1/2 space-y-1.5">
            {[1, 2, 3].map((n) => <span key={n} className={cn(chip, "block truncate text-center")}>{t("nav.sources")} {n}</span>)}
          </div>
        </div>
      ) : (
        <div className="flex w-full max-w-[16rem] flex-col gap-2">
          <span className="self-start rounded-2xl rounded-bl-sm border border-border bg-surface px-4 py-3 shadow-sm"><span className={cn(bar, "w-24")} /></span>
          <span className="self-end rounded-2xl rounded-br-sm bg-accent px-4 py-3 text-accent-foreground shadow-sm"><span className="block h-2 w-28 rounded-full bg-accent-foreground/60" /><span className="mt-2 block h-2 w-20 rounded-full bg-accent-foreground/40" /></span>
          <div className="flex gap-1.5 self-end">
            <span className={chip}>{t("nav.sources")}</span>
          </div>
        </div>
      )}
    </div>
  );
}
