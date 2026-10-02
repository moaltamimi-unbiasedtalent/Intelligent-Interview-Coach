"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { RequirePlatformAdmin } from "@/components/auth/RequirePlatformAdmin";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { adminPermissions, visibleDestinations } from "@/lib/admin/capabilities";

/**
 * Capability-aware Admin shell (P10B-W10.1). English-only (AD-01).
 *
 * Navigation lists only destinations that are operational today AND permitted by the permissions the
 * server returned for this account. Frontend gating is UX only: the API authorises every request.
 */
export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const auth = useAuthOptional();
  const destinations = visibleDestinations(adminPermissions(auth?.account));

  return (
    <RequirePlatformAdmin>
      <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
        <nav aria-label="Admin" className="lg:sticky lg:top-4 lg:self-start">
          <ul className="flex flex-wrap gap-1 lg:flex-col">
            {destinations.map((d) => {
              const active = d.href === "/admin" ? pathname === "/admin" : pathname === d.href || pathname.startsWith(d.href + "/");
              return (
                <li key={d.id}>
                  <Link
                    href={d.href}
                    aria-current={active ? "page" : undefined}
                    className={
                      "flex min-h-[44px] flex-col justify-center rounded-[8px] border px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 " +
                      (active ? "border-accent bg-surface-2 text-foreground" : "border-transparent text-muted hover:bg-surface-2 hover:text-foreground")
                    }
                  >
                    <span>{d.label}</span>
                    <span className="text-xs font-normal text-muted">{d.description}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="min-w-0">{children}</div>
      </div>
    </RequirePlatformAdmin>
  );
}
