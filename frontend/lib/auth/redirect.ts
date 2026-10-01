/**
 * Redirect that is VERIFIED to have landed (P10B-W9.7B).
 *
 * A soft `router.replace()` issued very early after page load (~100-300 ms, i.e. as soon as `/auth/me`
 * resolves during hydration) is occasionally dropped by the Next.js app router: no navigation happens, no
 * error is thrown, and because the route guard's effect depends only on resolved state it never re-runs, so
 * the redirect would be lost permanently. Reproduced at ~8% of page loads on a 2-vCPU Linux runner (Node 20,
 * production build); the failing trace shows exactly one `router.replace` call and no `history.replaceState`.
 * The user is then left on a page the guard meant to move them off: a new account on /prepare instead of
 * /onboarding, or an anonymous visitor stuck on the "checking your session" placeholder.
 *
 * So: issue the soft navigation, then verify the pathname actually changed; retry the soft navigation once;
 * finally fall back to a hard navigation. A dropped soft navigation has no side effects, so retrying is
 * idempotent. Returns a cleanup that cancels the verification (called when the guard's inputs change or the
 * guard unmounts, e.g. because the soft navigation did succeed).
 */

export const REDIRECT_VERIFY_MS = 500;

export interface ReplaceRouter {
  replace: (href: string) => void;
}

export function redirectVerified(
  router: ReplaceRouter,
  target: string,
  opts: {
    getPathname?: () => string;
    hardNavigate?: (href: string) => void;
    intervalMs?: number;
  } = {},
): () => void {
  const getPathname = opts.getPathname ?? (() => window.location.pathname);
  const hardNavigate = opts.hardNavigate ?? ((href: string) => window.location.replace(href));
  const targetPath = target.split("?")[0];

  router.replace(target);
  let checks = 0;
  const id = setInterval(() => {
    if (getPathname() === targetPath) {
      clearInterval(id);
      return;
    }
    checks += 1;
    if (checks === 1) {
      router.replace(target); // soft retry
    } else {
      clearInterval(id);
      hardNavigate(target); // guaranteed hard navigation
    }
  }, opts.intervalMs ?? REDIRECT_VERIFY_MS);
  return () => clearInterval(id);
}
