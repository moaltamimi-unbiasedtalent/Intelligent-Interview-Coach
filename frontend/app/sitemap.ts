import type { MetadataRoute } from "next";

// Public sitemap (Capstone P8 §43) — marketing surfaces only; never authenticated pages.
const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://ask4mo.example.com";
const PATHS = ["/", "/product", "/pricing", "/trust", "/privacy", "/terms", "/ai-transparency", "/about", "/help"];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return PATHS.map((p) => ({
    url: `${SITE}${p === "/" ? "" : p}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: p === "/" ? 1 : 0.6,
  }));
}
