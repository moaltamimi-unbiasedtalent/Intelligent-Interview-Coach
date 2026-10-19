"use client";

import Link from "@/components/ui/VerifiedLink";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { RequirePlatformAdmin } from "@/components/auth/RequirePlatformAdmin";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { adminPermissions, visibleDestinations } from "@/lib/admin/capabilities";

/**
 * Capability-aware Admin shell (P10B-W10.1). English-only (AD-01).
 *
 * Navigation lists only destinations that are operational today AND permitted by the permissions the server returned for this account. Frontend gating is UX only:
 * the API authorises every request.
 *
 * W12.5 (F-03): below the `lg` breakpoint the destinations collapse behind one "Admin menu" disclosure button that names the current page, instead of stacking about
 * 750 px of links above the content. Every authorised destination stays in the DOM and reachable by keyboard; Escape closes the menu and returns focus to the button.
 * At `lg` and above the list is always visible, as before.
 */
export function AdminNavShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const auth = useAuthOptional();
  const destinations = visibleDestinations(adminPermissions(auth?.account));
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { setOpen(false); }, [pathname]);
  const isActive = (href: string) => (href === "/admin" ? pathname === "/admin" : pathname === href || pathname.startsWith(href + "/"));
  const current = destinations.find((d) => isActive(d.href));

  return (
    <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
      <nav aria-label="Admin" className="lg:sticky lg:top-4 lg:self-start"
        onKeyDown={(e) => { if (e.key === "Escape" && open) { setOpen(false); button.current?.focus(); } }}>
        <button ref={button} type="button" aria-expanded={open} aria-controls="admin-nav-list" onClick={() => setOpen((o) => !o)}
          className="flex min-h-[44px] w-full items-center justify-between rounded-[8px] border border-border px-3 text-left text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 lg:hidden">
          <span>Admin menu: {current ? current.label : "choose a section"}</span>
          <span aria-hidden="true">{open ? "Close" : "Open"}</span>
        </button>
        <ul id="admin-nav-list" className={(open ? "mt-2 flex" : "hidden") + " max-h-[70vh] flex-col gap-1 overflow-y-auto lg:mt-0 lg:flex lg:max-h-none lg:overflow-visible"}>
          {destinations.map((d) => {
            const active = isActive(d.href);
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
  );
}

export function AdminShell({ children }: { children: ReactNode }) {
  return (
    <RequirePlatformAdmin>
      <AdminNavShell>{children}</AdminNavShell>
    </RequirePlatformAdmin>
  );
}
