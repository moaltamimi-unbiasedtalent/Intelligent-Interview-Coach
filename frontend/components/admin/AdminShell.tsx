"use client";

import Link from "@/components/ui/VerifiedLink";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { RequirePlatformAdmin } from "@/components/auth/RequirePlatformAdmin";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { adminPermissions, breadcrumbsFor, currentDestination, filterDestinations, groupedDestinations } from "@/lib/admin/capabilities";

/**
 * Capability-aware, grouped Admin shell (P10B-W10.1, W12.5, 03A). English-only (AD-01).
 *
 * Navigation lists only destinations that are operational today AND permitted by the permissions the server returned for this account; a section with no visible
 * destination is not rendered. Frontend gating is UX only: the API authorises every request.
 *
 * 03A: the destinations are arranged in the six owner-approved sections (ADMIN_GROUPS). Each section is a disclosure (button with aria-expanded) that starts open and can be
 * collapsed; the section holding the current page is re-opened on navigation. A "Find a section" filter narrows the VISIBLE destinations only (it holds no data of its
 * own). Arrow keys, Home and End move between section buttons and links; Tab order is unchanged. A breadcrumb trail names the section and page.
 *
 * W12.5 (F-03): below the `lg` breakpoint the sidebar collapses behind one "Admin menu" disclosure button that names the current page. Every authorised destination stays
 * in the DOM and reachable by keyboard; Escape closes the menu and returns focus to the button. At `lg` and above the sidebar is always visible.
 */
const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2";

export function AdminNavShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const auth = useAuthOptional();
  const permissions = adminPermissions(auth?.account);
  const groups = groupedDestinations(permissions);
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [query, setQuery] = useState("");
  const button = useRef<HTMLButtonElement | null>(null);
  const nav = useRef<HTMLElement | null>(null);
  const filter = useRef<HTMLInputElement | null>(null);

  const flat = groups.flatMap((g) => g.destinations);
  const current = currentDestination(pathname, flat);
  const currentGroupId = groups.find((g) => g.destinations.some((d) => d.id === current?.id))?.group.id;
  const filtering = query.trim().length > 0;
  const shown = filtering ? filterDestinations(groups, query) : groups;
  const matches = shown.reduce((n, g) => n + g.destinations.length, 0);
  const crumbs = breadcrumbsFor(pathname, groups);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!currentGroupId) return;
    setCollapsed((prev) => {
      if (!prev.has(currentGroupId)) return prev;
      const next = new Set(prev);
      next.delete(currentGroupId);
      return next;
    });
  }, [currentGroupId, pathname]);

  const toggle = (id: string) => setCollapsed((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const items = (): HTMLElement[] =>
    Array.from(nav.current?.querySelectorAll<HTMLElement>("[data-nav-item]") ?? []).filter((el) => !el.closest("[hidden]"));

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    const target = e.target as HTMLElement;
    if (e.key === "Escape") {
      if (filtering && target === filter.current) { setQuery(""); return; }
      if (open) { setOpen(false); button.current?.focus(); }
      return;
    }
    const list = items();
    if ((e.key === "ArrowDown" || e.key === "Enter") && target === filter.current) {
      // ArrowDown goes to the first item; Enter (while filtering) goes to the first matching destination link.
      const first = e.key === "Enter" ? list.find((el) => el.tagName === "A") : list[0];
      if (first && (e.key === "ArrowDown" || filtering)) { e.preventDefault(); first.focus(); }
      return;
    }
    if (!target.hasAttribute("data-nav-item")) return;
    const i = list.indexOf(target);
    let next: HTMLElement | undefined;
    if (e.key === "ArrowDown") next = list[Math.min(i + 1, list.length - 1)];
    else if (e.key === "ArrowUp") next = i === 0 ? filter.current ?? undefined : list[i - 1];
    else if (e.key === "Home") next = list[0];
    else if (e.key === "End") next = list[list.length - 1];
    if (next) { e.preventDefault(); next.focus(); }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[240px_1fr]">
      <nav ref={nav} aria-label="Admin" className="lg:sticky lg:top-4 lg:self-start" onKeyDown={onKeyDown}>
        <button ref={button} type="button" aria-expanded={open} aria-controls="admin-nav-list" onClick={() => setOpen((o) => !o)}
          className={"flex min-h-[44px] w-full items-center justify-between rounded-[8px] border border-border px-3 text-left text-sm font-medium lg:hidden " + FOCUS}>
          <span>Admin menu: {current ? current.label : "choose a section"}</span>
          <span aria-hidden="true">{open ? "Close" : "Open"}</span>
        </button>
        <div id="admin-nav-list" className={(open ? "mt-2 flex" : "hidden") + " max-h-[70vh] flex-col gap-2 overflow-y-auto lg:mt-0 lg:flex lg:max-h-[calc(100vh-2rem)]"}>
          <div>
            <label htmlFor="admin-nav-filter" className="sr-only">Find a section</label>
            <input id="admin-nav-filter" ref={filter} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a section"
              autoComplete="off" className={"min-h-[44px] w-full rounded-[8px] border border-border bg-transparent px-3 text-sm " + FOCUS} />
            <p role="status" className="sr-only">{filtering ? (matches ? `${matches} ${matches === 1 ? "section" : "sections"} found` : "No section matches") : ""}</p>
            {filtering && matches === 0 ? <p className="px-1 pt-2 text-xs text-muted">No section matches &ldquo;{query.trim()}&rdquo;.</p> : null}
          </div>
          {shown.map(({ group, destinations }) => {
            const expanded = filtering || !collapsed.has(group.id);
            const listId = `admin-nav-group-${group.id}`;
            return (
              <div key={group.id}>
                <button type="button" data-nav-item aria-expanded={expanded} aria-controls={listId} onClick={() => toggle(group.id)}
                  className={"flex min-h-[44px] w-full items-center justify-between rounded-[8px] px-3 text-left text-xs font-semibold uppercase tracking-wide hover:bg-surface-2 " + FOCUS +
                    (group.id === currentGroupId ? " text-foreground" : " text-muted")}>
                  <span>{group.label}</span>
                  <span aria-hidden="true">{expanded ? "−" : "+"}</span>
                </button>
                <ul id={listId} hidden={!expanded} className={expanded ? "flex flex-col gap-1" : "hidden"}>
                  {destinations.map((d) => {
                    const active = d.id === current?.id;
                    return (
                      <li key={d.id}>
                        <Link
                          href={d.href}
                          data-nav-item
                          title={d.description}
                          aria-current={active ? "page" : undefined}
                          className={
                            "flex min-h-[44px] items-center rounded-[8px] border px-3 py-1.5 text-sm font-medium " + FOCUS + " " +
                            (active ? "border-accent bg-surface-2 text-foreground" : "border-transparent text-muted hover:bg-surface-2 hover:text-foreground")
                          }
                        >
                          {d.label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      </nav>
      <div className="min-w-0">
        {crumbs.length > 1 ? (
          <nav aria-label="Breadcrumb" className="mb-3">
            <ol className="flex flex-wrap items-center gap-1 text-xs text-muted">
              {crumbs.map((c, i) => {
                const last = i === crumbs.length - 1;
                return (
                  <li key={`${i}-${c.label}`} className="flex items-center gap-1">
                    {i > 0 ? <span aria-hidden="true">/</span> : null}
                    {c.href && !last ? (
                      <Link href={c.href} className={"rounded-[4px] underline-offset-2 hover:text-foreground hover:underline " + FOCUS}>{c.label}</Link>
                    ) : (
                      <span aria-current={last ? "page" : undefined} className={last ? "font-medium text-foreground" : undefined}>{c.label}</span>
                    )}
                  </li>
                );
              })}
            </ol>
          </nav>
        ) : null}
        {children}
      </div>
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
