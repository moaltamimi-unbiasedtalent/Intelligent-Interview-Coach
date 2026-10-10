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
    <nav aria-label={t("journeyCues.railLabel")} data-testid="journey-rail">
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-2 text-sm">
        {JOURNEY_STAGES.map((stage, i) => {
          const here = stage === current;
          const done = currentIndex > i;
          return (
            <li key={stage} className="flex items-center gap-1">
              <Link
                href={stageHref(stage, opportunityId)}
                aria-current={here ? "step" : undefined}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  here ? "border-accent bg-accent text-accent-foreground" : done ? "border-border bg-surface-2 text-foreground" : "border-border bg-surface text-muted hover:bg-surface-2",
                )}
              >
                <span aria-hidden="true" className="font-bold">{i + 1}</span>
                <span>{t(STAGE_LABEL_KEY[stage])}</span>
                {here ? <span className="sr-only"> ({t("journeyCues.youAreHere")})</span> : null}
              </Link>
              {i < JOURNEY_STAGES.length - 1 ? <span aria-hidden="true" className="text-muted">&rsaquo;</span> : null}
            </li>
          );
        })}
      </ol>
      {current ? <p className="mt-1 text-xs font-semibold text-accent" data-testid="you-are-here">{t("journeyCues.youAreHere")}: {t(STAGE_LABEL_KEY[current])}</p> : null}
    </nav>
  );
}
