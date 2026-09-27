import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { cookies } from "next/headers";
import { AppShell } from "@/components/layout/AppShell";
import { ThemeScript } from "@/components/layout/ThemeScript";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { LOCALE_COOKIE } from "@/lib/i18n/cookie";
import { DEFAULT_APP_LOCALE, toSupportedLocale } from "@/lib/i18n/locales";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://ask4mo.example.com"),
  title: {
    default: "Ask4Mo - Intelligent Interview Coach",
    template: "%s · Ask4Mo",
  },
  // Opportunity-centred, restrained (P10B Wave 7); brand rule: no em dash in customer-facing copy.
  description:
    "Prepare for a specific job in one place. Ask4Mo brings the role, company research, your evidence, coaching and realistic practice into a single Opportunity. Ask More. Be More.",
  applicationName: "Ask4Mo",
  // Icons derived from the canonical Ask4Mo mark (no new logo). See public/brand/ask4mo-mark.svg.
  icons: { icon: "/brand/ask4mo-mark.svg", shortcut: "/brand/ask4mo-mark.svg", apple: "/brand/ask4mo-mark.svg" },
  openGraph: {
    title: "Ask4Mo - Intelligent Interview Coach",
    description:
      "Prepare for a specific job in one Opportunity: the role, company research, your evidence, coaching and realistic practice. Ask More. Be More.",
    siteName: "Ask4Mo",
    type: "website",
    images: [{ url: "/brand/ask4mo-logo.svg", width: 1200, height: 630, alt: "Ask4Mo" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#1a5e63",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Initial interface locale from the anonymous cookie (the account preference, once
  // loaded, becomes authoritative client-side). Never trusts an unsupported value.
  const cookieStore = await cookies();
  const initialLocale =
    toSupportedLocale(cookieStore.get(LOCALE_COOKIE)?.value) ?? DEFAULT_APP_LOCALE;
  return (
    <html lang={initialLocale} className={inter.variable} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <AuthProvider>
          <I18nProvider initialLocale={initialLocale}>
            <AppShell>{children}</AppShell>
          </I18nProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
