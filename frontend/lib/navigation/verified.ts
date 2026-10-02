/**
 * Verified user navigation (P10B-W10.1 navigation reliability correction).
 *
 * Observed on CI (Linux, production build, loaded CPU): a plain left click on a Next `<Link>` shortly after
 * page load starts the soft navigation (the `/target?_rsc=` request and the page chunk are fetched, both
 * 200) but the App Router never commits it: no `history.pushState`, the URL stays on the old page, nothing
 * is thrown. Reproduced ~1 in 100 under CPU saturation; the failing trace shows the click, the RSC fetches
 * and no navigation. The same class of loss was already seen for guard redirects (`redirectVerified`).
 *
 * `verifyNavigation` is called AFTER the Link has started its own navigation. It never navigates when the
 * first attempt succeeds. If the user is still on the originating path after `intervalMs` it retries the soft
 * `router.push` once (idempotent: a dropped navigation has no side effect), and if that is also lost it falls
 * back to a hard navigation. Any change of pathname (to the target or to anywhere else, e.g. the user clicked
 * something different) ends the verification, so it can never fight a later navigation. Pushing preserves
 * normal browser-history semantics; redirects keep using `redirectVerified` (replace).
 */

export const NAVIGATION_VERIFY_MS = 500;

export interface PushRouter {
  push: (href: string) => void;
}

export function verifyNavigation(
  router: PushRouter,
  target: string,
  opts: {
    getPathname?: () => string;
    hardNavigate?: (href: string) => void;
    intervalMs?: number;
  } = {},
): () => void {
  const getPathname = opts.getPathname ?? (() => window.location.pathname);
  const hardNavigate = opts.hardNavigate ?? ((href: string) => window.location.assign(href));
  const targetPath = target.split(/[?#]/)[0];
  const from = getPathname();
  // Same-page or fragment-only links involve no path change to verify.
  if (!targetPath || targetPath === from) return () => {};

  let checks = 0;
  const id = setInterval(() => {
    if (getPathname() !== from) {
      clearInterval(id); // landed (on the target or elsewhere): nothing to correct
      return;
    }
    checks += 1;
    if (checks === 1) {
      router.push(target); // soft retry
    } else {
      clearInterval(id);
      hardNavigate(target); // guaranteed hard navigation
    }
  }, opts.intervalMs ?? NAVIGATION_VERIFY_MS);
  return () => clearInterval(id);
}
