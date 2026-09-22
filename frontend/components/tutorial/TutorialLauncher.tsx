"use client";

import { START_TOUR_EVENT } from "./TutorialController";

/** "Take the tour" — dispatches the start event the TutorialController listens for. */
export function TutorialLauncher({
  className,
  label = "Take the tour",
}: {
  className?: string;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent(START_TOUR_EVENT))}
      className={
        className ??
        "min-h-[44px] rounded bg-accent px-[18px] text-[15px] font-semibold text-accent-foreground"
      }
    >
      {label}
    </button>
  );
}
