"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { useT } from "@/components/i18n/I18nProvider";

/**
 * Canonical Ask4Mo brand lockup (P10B Wave 1). ONE implementation used across marketing, the
 * authenticated app, auth pages and mobile — the real vector mark + wordmark, never an emoji
 * substitute. `href` lets the marketing chrome link to `/` and the app chrome to `/app`.
 */
export function Logo({
  href,
  className,
  markClassName,
}: {
  href: string;
  className?: string;
  markClassName?: string;
}) {
  const t = useT();
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-2.5 font-bold tracking-tight text-foreground",
        className,
      )}
      aria-label={t("common.homeAria")}
      data-testid="ask4mo-logo"
    >
      {/* Decorative mark; the link's aria-label carries the accessible name and the wordmark
          is the visible fallback. A plain <img> is intentional for this tiny static SVG. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/ask4mo-mark.svg"
        alt=""
        aria-hidden="true"
        width={30}
        height={30}
        className={cn("h-7 w-7 sm:h-[30px] sm:w-[30px]", markClassName)}
      />
      <span>Ask4Mo</span>
    </Link>
  );
}
