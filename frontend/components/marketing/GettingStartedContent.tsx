"use client";

import Image from "next/image";
import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { CandidateStory } from "@/components/marketing/CandidateStory";
import { WorkflowMap } from "@/components/marketing/WorkflowMap";

// v4 Getting Started: short hero, static candidate story, interactive workflow map, six visual steps, a first-15-minutes
// checklist and links to Help, Trust and AI transparency. Imagery: editorial illustrations explain the system; the
// candidate story is a fictional, AI-generated still sequence (no video, no testimonial).

const STEPS: { n: number; image?: { src: string; altKey: string; w: number; h: number } }[] = [
  { n: 1 },
  { n: 2 },
  { n: 3, image: { src: "/images/ask4mo/ask4mo-v4-trust-evidence-editorial.png", altKey: "gettingStarted.step3Alt", w: 1536, h: 1024 } },
  { n: 4 },
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
            {STEPS.map(({ n, image }) => (
              <li key={n} className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface">
                {image ? (
                  <Image src={image.src} alt={t(image.altKey)} width={image.w} height={image.h} sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 380px" className="h-44 w-full object-cover" />
                ) : null}
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
            <li><Link href="/help" className="hover:underline">{t("gettingStarted.linkHelp")}</Link></li>
            <li><Link href="/trust" className="hover:underline">{t("gettingStarted.linkTrust")}</Link></li>
            <li><Link href="/ai-transparency" className="hover:underline">{t("gettingStarted.linkAi")}</Link></li>
          </ul>
          <div className="mt-8"><ButtonLink href="/register">{t("gettingStarted.ctaPrimary")}</ButtonLink></div>
        </div>
      </section>
    </div>
  );
}
