"use client";

import Link from "@/components/ui/VerifiedLink";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/components/i18n/I18nProvider";
import { PRIMARY_NAV } from "./nav-items";

/**
 * Compact bottom navigation for mobile — a deliberate pattern, not a compressed
 * desktop header. Hidden on md+ where the header nav is used. 44px touch targets.
 */
export function MobileNavigation() {
  const pathname = usePathname();
  const t = useT();
  return (
    <nav
      aria-label={t("nav.primary")}
      className="fixed inset-x-0 bottom-0 z-30 grid border-t border-border bg-surface md:hidden"
      style={{ gridTemplateColumns: `repeat(${PRIMARY_NAV.length}, minmax(0, 1fr))` }}
    >
      {PRIMARY_NAV.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        const label = t(item.labelKey);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            // Explicit accessible name = the full concept label, so it is never ambiguous even if the
            // visible text is tight at ~390px (P10B-W9.4 / H).
            aria-label={label}
            className={cn(
              "flex min-h-[52px] flex-col items-center justify-center gap-0.5 px-1 py-2 font-medium transition-colors",
              // Inactive uses a legible default (not muted grey) so Opportunities is discoverable.
              active ? "text-accent" : "text-foreground/70",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                active ? "bg-accent" : "bg-transparent",
              )}
            />
            {/* Full word kept (no ambiguous ellipsis); slightly smaller + tighter so "Opportunities"
                fits a 5-column bar at ~390px. */}
            <span className="max-w-full text-center text-[11px] leading-tight tracking-tight">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
