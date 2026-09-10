import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { AppShell } from "@/components/layout/AppShell";
import { ThemeScript } from "@/components/layout/ThemeScript";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
