"use client";

// Public marketing chrome (Capstone P8 §3/§4). A distinct header/footer for the public site,
// separate from the authenticated AppShell nav. Uses the shared i18n + design tokens. Shows a
// "Go to your workspace" link when the visitor is already signed in (no redirect loop).

import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { ButtonLink } from "@/components/ui/Button";
import { APP_HOME } from "@/lib/auth/routes";

const NAV = [
  { href: "/product", key: "marketing.navProduct" },
  { href: "/pricing", key: "marketing.navPricing" },
  { href: "/trust", key: "marketing.navTrust" },
  { href: "/about", key: "marketing.navAbout" },
  { href: "/help", key: "marketing.navHelp" },
] as const;

function MarketingHeader() {
  const t = useT();
  const auth = useAuthOptional();
  const authed = auth?.status === "authenticated";
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold" aria-label="Ask4Mo — home">
          <span aria-hidden>🎯</span>
          <span>Ask4Mo</span>
        </Link>
        <nav aria-label="Marketing" className="hidden items-center gap-5 md:flex">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="text-sm text-muted hover:text-foreground">
              {t(item.key)}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          {authed ? (
            <ButtonLink href={APP_HOME} size="sm">{t("marketing.goToApp")}</ButtonLink>
          ) : (
            <>
              <Link href="/sign-in" className="text-sm font-medium text-foreground hover:underline">
                {t("marketing.signIn")}
              </Link>
              <ButtonLink href="/register" size="sm">{t("marketing.getStarted")}</ButtonLink>
            </>
          )}
        </div>
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
      <main id="main" className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}
