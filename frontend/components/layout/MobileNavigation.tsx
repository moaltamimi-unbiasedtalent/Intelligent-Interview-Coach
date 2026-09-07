"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { PRIMARY_NAV } from "./nav-items";

/**
 * Compact bottom navigation for mobile — a deliberate pattern, not a compressed
 * desktop header. Hidden on md+ where the header nav is used. 44px touch targets.
 */
export function MobileNavigation() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-border bg-surface md:hidden"
    >
      {PRIMARY_NAV.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex min-h-[52px] flex-col items-center justify-center gap-0.5 px-2 py-2 text-xs font-medium transition-colors",
              active ? "text-accent" : "text-muted",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                active ? "bg-accent" : "bg-transparent",
              )}
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
