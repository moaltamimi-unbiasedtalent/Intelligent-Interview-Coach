"use client";

import type { ReactNode } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { useMediaQuery } from "@/lib/useMediaQuery";

/**
 * Desktop: conversation + context rail side by side. Mobile: a Coach / Preparation
 * tab set (not a compressed desktop layout, no complex bottom sheet in Phase 3B/3C).
 * Each panel is rendered exactly once (media-query driven) — no duplicated DOM or
 * duplicate element ids. Falls back to the desktop layout before mount (SSR-safe).
 */
export function PrepareResponsive({
  coach,
  context,
}: {
  coach: ReactNode;
  context: ReactNode;
}) {
  const isMobile = useMediaQuery("(max-width: 767px)");

  if (isMobile) {
    return (
      <Tabs
        items={[
          { id: "coach", label: "Mo", content: coach },
          { id: "prep", label: "Preparation", content: <div className="grid gap-4">{context}</div> },
        ]}
      />
    );
  }

  return (
    <div className="grid gap-5 md:grid-cols-[1fr_340px] md:items-start">
      <div>{coach}</div>
      <aside className="grid gap-4">{context}</aside>
    </div>
  );
}
