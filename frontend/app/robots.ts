import type { MetadataRoute } from "next";

// SEO robots policy (Capstone P8 §43). Public marketing is crawlable; authenticated candidate
// pages, admin and reviewer diagnostics are disallowed (they are also behind auth server-side).
const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://ask4mo.example.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/app",
          "/prepare",
          "/practice",
          "/progress",
          "/history",
          "/documents",
          "/workspaces",
          "/sources",
          "/settings",
          "/account",
          "/admin",
          "/review",
        ],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
