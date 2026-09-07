"use client";

import type { ReactNode } from "react";
import { Tabs } from "@/components/ui/Tabs";

/**
 * Desktop: conversation + context rail side by side. Mobile: a Coach / Preparation
 * tab set (not a compressed desktop layout, no complex bottom sheet in Phase 3B).
 * The conversation stays primary; context is one tap away.
 */
export function PrepareResponsive({
  coach,
  context,
}: {
  coach: ReactNode;
  context: ReactNode;
}) {
  return (
    <>
      <div className="hidden gap-5 md:grid md:grid-cols-[1fr_340px] md:items-start">
        <div>{coach}</div>
        <aside className="grid gap-4">{context}</aside>
      </div>
      <div className="md:hidden">
        <Tabs
          items={[
            { id: "coach", label: "Coach", content: coach },
            { id: "prep", label: "Preparation", content: <div className="grid gap-4">{context}</div> },
          ]}
        />
      </div>
    </>
  );
}
