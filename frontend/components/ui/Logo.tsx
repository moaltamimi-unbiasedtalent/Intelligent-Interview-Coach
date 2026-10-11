"use client";

import Link from "@/components/ui/VerifiedLink";

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
        "inline-flex items-center gap-3 text-xl font-bold tracking-tight text-foreground",
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
        width={45}
        height={45}
        className={cn("h-10 w-10 sm:h-[45px] sm:w-[45px]", markClassName)}
      />
      <span>Ask4Mo</span>
    </Link>
  );
}
