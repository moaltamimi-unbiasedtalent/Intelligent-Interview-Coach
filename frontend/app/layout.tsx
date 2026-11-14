import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { cookies, headers } from "next/headers";
import { AppShell } from "@/components/layout/AppShell";
import { ThemeScript } from "@/components/layout/ThemeScript";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { BRAND_SLOGAN } from "@/lib/brand";
import { getCatalog } from "@/lib/i18n/catalog";
import { LOCALE_COOKIE } from "@/lib/i18n/cookie";
import { deploymentMetadata } from "@/lib/deploymentMetadata";
import { DEFAULT_APP_LOCALE, toActiveLocale, type AppLocale } from "@/lib/i18n/locales";
import "./globals.css";

// P10B-W9.7A: the SAME Inter family now also loads its `cyrillic` subset so Russian copy renders in Inter
// instead of the system fallback (W9.7 finding). next/font self-hosts the subset at build time; the browser
// downloads it only when a page actually contains Cyrillic (unicode-range), so Latin-only users pay nothing.
// No new family and no manually distributed font file.
const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
  display: "swap",
});

// Request-specific nonces cannot be served from static HTML/ISR caches.
export const dynamic = "force-dynamic";

const metadataBase = new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://ask4mo.example.com");

async function requestLocale() {
  // This cookie supplies the server's initial locale until the account preference loads.
  const cookieStore = await cookies();
  return toActiveLocale(cookieStore.get(LOCALE_COOKIE)?.value) ?? DEFAULT_APP_LOCALE;
}

function rootMetadata(locale: AppLocale): Metadata {
  const { common, marketing } = getCatalog(locale);
  const title = `Ask4Mo - ${common.productName}`;
  const description = `${marketing.heroSubtitle} ${BRAND_SLOGAN}`;

  return {
    metadataBase,
    title: { default: title, template: "%s · Ask4Mo" },
    description,
    applicationName: "Ask4Mo",
    // Icons derived from the canonical Ask4Mo mark (no new logo). See public/brand/ask4mo-mark.svg.
    icons: { icon: "/brand/ask4mo-mark.svg", shortcut: "/brand/ask4mo-mark.svg", apple: "/brand/ask4mo-mark.svg" },
    openGraph: {
      title,
      description,
      siteName: "Ask4Mo",
      type: "website",
      images: [{ url: "/brand/ask4mo-logo.svg", width: 1200, height: 630, alt: "Ask4Mo" }],
    },
    other: deploymentMetadata(),
  };
}

export async function generateMetadata(): Promise<Metadata> {
  return rootMetadata(await requestLocale());
}

export const viewport: Viewport = {
  themeColor: "#1a5e63",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const initialLocale = await requestLocale();
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang={initialLocale} className={inter.variable} suppressHydrationWarning>
      <head>
        <ThemeScript nonce={nonce} />
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
