"use client";

import { useEffect, useState } from "react";

/**
 * SSR-safe media query. Returns `false` on the server and first client render
 * (so markup matches), then reflects the real match after mount. Used to render a
 * single responsive layout (no duplicated DOM / duplicate ids).
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(query);
    const update = () => setMatches(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, [query]);

  return matches;
}
