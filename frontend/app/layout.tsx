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
    default: "Ask4Mo — Intelligent Interview Coach",
    template: "%s · Ask4Mo",
  },
  description: "AI-powered interview preparation, practice and feedback. Ask More. Be More.",
  openGraph: {
    title: "Ask4Mo — Intelligent Interview Coach",
    description: "Prepare with evidence, practise with purpose, improve with feedback. Ask More. Be More.",
    siteName: "Ask4Mo",
    type: "website",
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
