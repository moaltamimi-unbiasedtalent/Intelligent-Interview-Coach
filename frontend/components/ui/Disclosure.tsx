"use client";

import { useId, useState } from "react";
import type { ReactNode } from "react";

/**
 * Accessible progressive-disclosure control (Capstone P2/E2).
 *
 * A button toggles a region: `aria-expanded` + `aria-controls` wire the button to
 * the region; the region keeps its `id` and is present in the DOM only when open
 * (collapsed content is not rendered, so it is never copied into storage and is
 * removed cleanly). Fully keyboard operable (it is a native <button>), and there is
 * no motion to disable. Content is NEVER destroyed — toggling re-renders `children`.
 */
export function Disclosure({
  children,
  showLabel = "Show more",
  hideLabel = "Show less",
  defaultOpen = false,
  className,
}: {
  children: ReactNode;
  showLabel?: string;
  hideLabel?: string;
  defaultOpen?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const regionId = useId();

  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
      >
        {open ? hideLabel : showLabel}
        <span aria-hidden>{open ? "▲" : "▾"}</span>
      </button>
      {open ? (
        <div id={regionId} className="mt-2">
          {children}
        </div>
      ) : (
        // Keep the region referenceable for assistive tech even when collapsed.
        <div id={regionId} hidden />
      )}
    </div>
  );
}
