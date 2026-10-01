"use client";

import { cn } from "@/lib/utils";
import { useT } from "@/components/i18n/I18nProvider";

const STAGES = ["Understand", "Prepare", "Practise", "Review"] as const;
type Stage = (typeof STAGES)[number];

const STAGE_KEY: Record<Stage, string> = {
  Understand: "prepare.stageUnderstand",
  Prepare: "prepare.stagePrepare",
  Practise: "prepare.stagePractise",
  Review: "prepare.stageReview",
};

/** Lightweight stage cue (borrowed from Guided Journey) — never heavy chrome. */
export function StageProgress({ current }: { current: Stage }) {
  const t = useT();
  const currentIndex = STAGES.indexOf(current);
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" aria-label={t("prepare.progressStagesAria")}>
      {STAGES.map((stage, i) => {
        const done = i < currentIndex;
        const active = i === currentIndex;
        return (
          <li key={stage} className="flex items-center gap-2">
            <span
              className={cn(
                "grid h-5 w-5 place-items-center rounded-full text-[11px] font-bold",
                active
                  ? "bg-accent text-accent-foreground"
                  : done
                    ? "bg-surface-2 text-foreground"
                    : "bg-surface-2 text-muted",
              )}
              aria-hidden="true"
            >
              {done ? "✓" : i + 1}
            </span>
            <span className={cn(active ? "font-semibold text-foreground" : "text-muted")}>
              {t(STAGE_KEY[stage])}
            </span>
            {i < STAGES.length - 1 ? (
              <span aria-hidden="true" className="mx-1 text-border">
                —
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
