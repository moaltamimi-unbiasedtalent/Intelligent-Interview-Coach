"use client";

// Seven-stage preparation journey rail (v4). Existing routes and existing state only. `current` marks "You are here"
// (aria-current="step"); stages link to their existing surfaces. Compact, never heavy chrome, and never rendered inside
// an active practice question (the distraction-free flow is untouched).

import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";
import { JOURNEY_STAGES, STAGE_LABEL_KEY, stageHref, type JourneyStage } from "@/lib/journey";
import { cn } from "@/lib/utils";

export function JourneyRail({ current, opportunityId }: { current?: JourneyStage; opportunityId?: number | null }) {
  const t = useT();
  const currentIndex = current ? JOURNEY_STAGES.indexOf(current) : -1;
  return (
    <nav aria-label={t("journeyCues.railLabel")} data-testid="journey-rail" className="relative overflow-hidden rounded-[1.75rem] border border-border bg-surface/90 px-3 pb-4 pt-5 shadow-sm backdrop-blur-md">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#6f5687] via-[#1a5e63] to-[#d97d5c]" />
      <ol className="-mx-2 flex min-w-max overflow-x-auto px-2 pb-1 text-sm md:min-w-0">
        {JOURNEY_STAGES.map((stage, i) => {
          const here = stage === current;
          const done = currentIndex > i;
          return (
            <li key={stage} className="relative min-w-28 flex-1">
              {i < JOURNEY_STAGES.length - 1 ? (
                <span aria-hidden="true" className={cn("absolute left-1/2 top-4 h-px w-full", currentIndex > i ? "bg-accent" : "bg-border")} />
              ) : null}
              <Link
                href={stageHref(stage, opportunityId)}
                aria-current={here ? "step" : undefined}
                className={cn(
                  "relative z-10 flex w-full flex-col items-center gap-2 rounded-lg px-2 py-1 text-center text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  here ? "text-foreground" : done ? "text-foreground" : "text-muted hover:text-foreground",
                )}
              >
                <span aria-hidden="true" className={cn("grid h-8 w-8 place-items-center rounded-full border font-bold", here ? "border-accent bg-accent text-accent-foreground ring-4 ring-accent/10" : done ? "border-accent bg-[var(--brand-mint)] text-accent" : "border-border bg-surface text-muted")}>{i + 1}</span>
                <span>{t(STAGE_LABEL_KEY[stage])}</span>
                {here ? <span className="sr-only"> ({t("journeyCues.youAreHere")})</span> : null}
              </Link>
            </li>
          );
        })}
      </ol>
      {current ? <p className="mt-1 text-xs font-semibold text-accent" data-testid="you-are-here">{t("journeyCues.youAreHere")}: {t(STAGE_LABEL_KEY[current])}</p> : null}
    </nav>
  );
}
