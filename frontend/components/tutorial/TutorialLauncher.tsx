"use client";

import { START_TOUR_EVENT } from "./TutorialController";
import { useT } from "@/components/i18n/I18nProvider";

/** "Take the tour" - dispatches the start event the TutorialController listens for. */
export function TutorialLauncher({
  className,
  label,
}: {
  className?: string;
  label?: string;
}) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent(START_TOUR_EVENT))}
      className={
        className ??
        "min-h-[44px] rounded bg-accent px-[18px] text-[15px] font-semibold text-accent-foreground"
      }
    >
      {label ?? t("common.takeTour")}
    </button>
  );
}
