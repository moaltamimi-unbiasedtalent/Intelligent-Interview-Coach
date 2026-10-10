"use client";

// Public marketing chrome (Capstone P8 §3/§4; v4 floating navigation). A distinct header/footer for the
// public site, separate from the authenticated AppShell nav. The header FLOATS 20-24px from the top of the
// viewport, stays visible while scrolling and only compacts (never hides). It is used on marketing routes
// only, never inside authenticated Practice. Uses the shared i18n + design tokens. Shows a "Go to your
// workspace" link when the visitor is already signed in (no redirect loop).

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useT } from "@/components/i18n/I18nProvider";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { ButtonLink } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { LanguageMenu } from "@/components/i18n/LanguageMenu";
import { APP_HOME } from "@/lib/auth/routes";
import { cn } from "@/lib/utils";

export const MARKETING_NAV = [
  { href: "/product", key: "marketing.navProduct" },
  { href: "/getting-started", key: "v4nav.howItWorks" },
  { href: "/pricing", key: "marketing.navPricing" },
  { href: "/trust", key: "marketing.navTrust" },
  { href: "/about", key: "marketing.navAbout" },
  { href: "/help", key: "marketing.navHelp" },
] as const;

/** Distance of the floating bar from the viewport top; anchors are offset so headings are never covered. */
const SCROLL_PADDING_TOP = "7rem";

function MarketingHeader() {
  const t = useT();
  const auth = useAuthOptional();
  const authed = auth?.status === "authenticated";
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Compact (never hide) after the first few pixels of scroll.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Anchor offset for the floating bar (restored on unmount so the app shell is unaffected).
  useEffect(() => {
    const root = document.documentElement;
    const previous = root.style.scrollPaddingTop;
    root.style.scrollPaddingTop = SCROLL_PADDING_TOP;
    return () => { root.style.scrollPaddingTop = previous; };
  }, []);

  const close = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) toggleRef.current?.focus();
  }, []);

  // Mobile menu: focus the first link on open; Escape closes and returns focus; Tab is kept inside the menu.
  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("a,button")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); close(true); return; }
      if (e.key !== "Tab") return;
      const items = [toggleRef.current, ...Array.from(panelRef.current?.querySelectorAll<HTMLElement>("a,button") ?? [])]
        .filter((x): x is HTMLElement => !!x);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && active === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  return (
    <header
      className="sticky top-0 z-50 px-3 pt-5 sm:px-4"
      data-testid="marketing-header"
      data-scrolled={scrolled ? "true" : "false"}
    >
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-[60] focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-accent-foreground focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-accent"
      >
        {t("v4nav.skipToContent")}
      </a>
      <div
        ref={wrapRef}
        className={cn(
          "mx-auto max-w-content rounded-2xl border border-border bg-surface/90 backdrop-blur-md transition-all duration-200 motion-reduce:transition-none",
          scrolled ? "shadow-soft backdrop-blur-xl bg-surface/95" : "shadow-sm",
        )}
      >
        <div className={cn("flex items-center justify-between gap-4 px-4 transition-all duration-200 motion-reduce:transition-none", scrolled ? "py-2" : "py-3")}>
          <Logo href="/" />
          <nav aria-label={t("marketing.navAria")} className="hidden items-center gap-5 lg:flex">
            {MARKETING_NAV.map((item) => (
              <Link key={item.href} href={item.href} className="rounded text-sm text-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                {t(item.key)}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            {/* Global language control - anonymous visitors can switch the marketing language. */}
            <LanguageMenu />
            {authed ? (
              <ButtonLink href={APP_HOME} size="sm">{t("marketing.goToApp")}</ButtonLink>
            ) : (
              <>
                <Link href="/sign-in" className="hidden rounded text-sm font-medium text-foreground hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:inline">
                  {t("marketing.signIn")}
                </Link>
                <ButtonLink href="/register" size="sm">{t("marketing.getStarted")}</ButtonLink>
              </>
            )}
            <button
              ref={toggleRef}
              type="button"
              className="inline-flex h-9 items-center rounded-md border border-border px-3 text-sm font-medium text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent lg:hidden"
              aria-label={t("v4nav.menuLabel")}
              aria-expanded={open}
              aria-controls="marketing-mobile-menu"
              onClick={() => (open ? close(false) : setOpen(true))}
            >
              {/* Stable name (WCAG label-in-name); aria-expanded conveys the open state. */}
              <span>{t("v4nav.menuButton")}</span>
            </button>
          </div>
        </div>
        {open ? (
          <div ref={panelRef} id="marketing-mobile-menu" className="border-t border-border px-4 pb-3 pt-2 lg:hidden">
            {/* Accessible mobile menu: the desktop nav is hidden below lg, so the links live here. */}
            <nav aria-label={t("marketing.navAriaMobile")}>
              <ul className="grid gap-1">
                {MARKETING_NAV.map((item) => (
                  <li key={item.href}>
                    <Link href={item.href} onClick={() => close(false)} className="block rounded px-2 py-2 text-sm text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                      {t(item.key)}
                    </Link>
                  </li>
                ))}
                {!authed ? (
                  <li>
                    <Link href="/sign-in" onClick={() => close(false)} className="block rounded px-2 py-2 text-sm font-medium text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                      {t("marketing.signIn")}
                    </Link>
                  </li>
                ) : null}
              </ul>
            </nav>
          </div>
        ) : null}
      </div>
    </header>
  );
}

function MarketingFooter() {
  const t = useT();
  const year = new Date().getFullYear();
  return (
    <footer className="mt-16 border-t border-border bg-surface">
      <div className="mx-auto grid max-w-content gap-8 px-4 py-10 sm:grid-cols-2 md:grid-cols-4">
        <div>
          <p className="font-semibold">Ask4Mo</p>
          <p className="mt-1 text-sm text-muted">{t("marketing.footerTagline")}</p>
        </div>
        <div>
          <p className="text-sm font-semibold">{t("marketing.footerProduct")}</p>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            <li><Link href="/product" className="hover:text-foreground">{t("marketing.navProduct")}</Link></li>
            <li><Link href="/getting-started" className="hover:text-foreground">{t("v4nav.howItWorks")}</Link></li>
            <li><Link href="/pricing" className="hover:text-foreground">{t("marketing.navPricing")}</Link></li>
            <li><Link href="/help" className="hover:text-foreground">{t("marketing.navHelp")}</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold">{t("marketing.footerCompany")}</p>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            <li><Link href="/about" className="hover:text-foreground">{t("marketing.navAbout")}</Link></li>
            <li><Link href="/trust" className="hover:text-foreground">{t("marketing.footerTrust")}</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold">{t("marketing.footerLegal")}</p>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            <li><Link href="/privacy" className="hover:text-foreground">{t("marketing.footerPrivacy")}</Link></li>
            <li><Link href="/terms" className="hover:text-foreground">{t("marketing.footerTerms")}</Link></li>
            <li><Link href="/ai-transparency" className="hover:text-foreground">{t("marketing.footerAi")}</Link></li>
          </ul>
        </div>
      </div>
      <div className="mx-auto max-w-content px-4 pb-8 text-xs text-muted">
        <p>© {year} Ask4Mo. {t("marketing.footerRights")}</p>
        <p className="mt-1">{t("marketing.footerNoBilling")} {t("marketing.footerDraft")}</p>
      </div>
    </footer>
  );
}

export function MarketingShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <MarketingHeader />
      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">{children}</main>
      <MarketingFooter />
    </div>
  );
}
