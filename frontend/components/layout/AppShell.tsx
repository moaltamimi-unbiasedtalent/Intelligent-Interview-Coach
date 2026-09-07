import Link from "next/link";
import type { ReactNode } from "react";
import { Brand } from "./Brand";
import { MobileNavigation } from "./MobileNavigation";
import { PrimaryNavigation } from "./PrimaryNavigation";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Restrained product shell: a quiet top header (wordmark · primary nav · theme ·
 * account) and a content region. Mobile uses a bottom nav instead of the header
 * nav. No giant sidebar + giant header — one quiet header only.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-[8px] focus:bg-surface focus:px-3 focus:py-2 focus:shadow-soft"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-20 border-b border-border bg-surface">
        <div className="mx-auto flex max-w-content items-center gap-4 px-5 py-3">
          <Brand />
          <div className="ml-auto flex items-center gap-3">
            <PrimaryNavigation />
            <ThemeToggle />
            <Link
              href="/settings"
              aria-label="Account and settings"
              className="grid h-8 w-8 place-items-center rounded-full bg-secondary text-xs font-bold text-[#3a3324]"
            >
              MA
            </Link>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-content px-5 pb-28 pt-7 md:pb-20">
        {children}
      </main>
      <MobileNavigation />
    </div>
  );
}
