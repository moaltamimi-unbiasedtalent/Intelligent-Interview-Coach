"use client";

import { Suspense, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { Brand } from "./Brand";
import { MobileNavigation } from "./MobileNavigation";
import { MoreMenu } from "./MoreMenu";
import { PrimaryNavigation } from "./PrimaryNavigation";
import { ThemeToggle } from "./ThemeToggle";
import { TutorialController } from "@/components/tutorial/TutorialController";
import { AccountMenu } from "@/components/auth/AccountMenu";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { MarketingShell } from "@/components/marketing/MarketingShell";
import { isMarketingRoute } from "@/lib/auth/routes";

/**
 * Chrome router (Capstone P8 §3). Public marketing routes render the marketing chrome
 * (its own header/footer, no app nav, no RouteGuard); everything else renders the
 * restrained product shell — a quiet top header (wordmark · primary nav · theme · account)
 * and a guarded content region, with a mobile bottom nav.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  if (isMarketingRoute(pathname)) {
    return <MarketingShell>{children}</MarketingShell>;
  }
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
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <PrimaryNavigation />
            {/* Supporting destinations (Sources, Review & Diagnostics) — available on
                desktop and mobile without crowding the primary nav / bottom bar. */}
            <MoreMenu />
            <ThemeToggle />
            <AccountMenu />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-content px-5 pb-28 pt-7 md:pb-20">
        {/* RouteGuard reads the URL (useSearchParams); a Suspense boundary keeps
            static prerender (e.g. /_not-found) from bailing the whole page to CSR. */}
        <Suspense fallback={children}>
          <RouteGuard>{children}</RouteGuard>
        </Suspense>
      </main>
      <MobileNavigation />
      <TutorialController />
    </div>
  );
}
