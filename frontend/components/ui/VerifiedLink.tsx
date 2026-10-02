"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ComponentProps, MouseEvent } from "react";
import { verifyNavigation } from "@/lib/navigation/verified";

/**
 * Drop-in replacement for `next/link` on app-shell navigation (header, menus, wordmark, admin nav).
 * Rendering, `href` semantics, prefetching, modified clicks (new tab/window) and keyboard activation are
 * exactly `next/link`; on a plain same-tab click it additionally verifies the soft navigation landed and
 * recovers a dropped one (see `lib/navigation/verified.ts`).
 */
export default function VerifiedLink({ onClick, href, target, ...rest }: ComponentProps<typeof Link>) {
  const router = useRouter();
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    const plain = e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
    if (e.defaultPrevented || !plain || (target && target !== "_self")) return;
    if (typeof href === "string" && href.startsWith("/")) verifyNavigation(router, href);
  };
  return <Link {...rest} href={href} target={target} onClick={handle} />;
}
