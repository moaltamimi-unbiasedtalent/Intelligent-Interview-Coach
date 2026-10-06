"use client";

import Link from "@/components/ui/VerifiedLink";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useT } from "@/components/i18n/I18nProvider";
import { PRIMARY_NAV } from "./nav-items";

/** Desktop header navigation (shown from lg = 1024px; below that, tablet and mobile use the compact bottom bar). */
export function PrimaryNavigation() {
  const pathname = usePathname();
  const t = useT();
  return (
    <nav aria-label={t("nav.primary")} className="hidden items-center gap-1 lg:flex">
      {PRIMARY_NAV.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              // P10B-W9.4: inactive items use a legible default (not muted grey) so the primary
              // nav reads as navigation and the first item (Opportunities) is discoverable, without
              // making any item look disabled. Active state unchanged.
              "rounded-[8px] px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "bg-surface-2 text-foreground"
                : "text-foreground/80 hover:text-foreground hover:bg-surface-2",
            )}
          >
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}
