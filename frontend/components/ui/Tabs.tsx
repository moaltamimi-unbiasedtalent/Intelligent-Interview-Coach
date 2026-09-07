"use client";

import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

/** Accessible tabs (role=tablist/tab/tabpanel) with arrow-key navigation. */
export function Tabs({ items, className }: { items: TabItem[]; className?: string }) {
  const [active, setActive] = useState(items[0]?.id);
  const base = useId();

  function onKeyDown(e: React.KeyboardEvent) {
    const idx = items.findIndex((i) => i.id === active);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const delta = e.key === "ArrowRight" ? 1 : -1;
      const next = items[(idx + delta + items.length) % items.length];
      setActive(next.id);
      document.getElementById(`${base}-tab-${next.id}`)?.focus();
    }
  }

  return (
    <div className={className}>
      <div
        role="tablist"
        aria-label="Sections"
        onKeyDown={onKeyDown}
        className="inline-flex gap-1 rounded-full bg-surface-2 p-1"
      >
        {items.map((item) => {
          const selected = item.id === active;
          return (
            <button
              key={item.id}
              id={`${base}-tab-${item.id}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`${base}-panel-${item.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(item.id)}
              className={cn(
                "min-h-[40px] rounded-full px-4 text-sm font-semibold transition-colors",
                selected ? "bg-surface text-foreground shadow-soft" : "text-muted",
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          id={`${base}-panel-${item.id}`}
          role="tabpanel"
          aria-labelledby={`${base}-tab-${item.id}`}
          hidden={item.id !== active}
          className="mt-4"
        >
          {item.id === active ? item.content : null}
        </div>
      ))}
    </div>
  );
}
