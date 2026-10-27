/** Narrow test-only classification; never exempts images, APIs or uncommitted navigation. */
export function completedPracticeRscAbort(event: Record<string, unknown>, confirmedUrl: string | null): boolean {
  if (!confirmedUrl || event.code !== "net::ERR_ABORTED" || event.resource !== "fetch" ||
      event.rsc !== true || event.status !== 200 || event.contentType !== "text/x-component" || typeof event.url !== "string") return false;
  try {
    const request = new URL(event.url), confirmed = new URL(confirmedUrl);
    return request.origin === confirmed.origin && request.pathname === "/practice" && confirmed.pathname === "/practice";
  } catch { return false; }
}
