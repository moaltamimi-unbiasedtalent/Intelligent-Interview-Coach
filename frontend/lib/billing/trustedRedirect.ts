// The ONLY hosts the browser may be sent to for a hosted checkout. A redirect URL comes from our own API, but it is still validated here so a
// compromised or malformed response can never turn the Continue button into an open redirect. https only, no credentials, exact host allow-list.
const ALLOWED_CHECKOUT_HOSTS = ["checkout.stripe.com"];

export function trustedCheckoutUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (u.protocol !== "https:" || u.username || u.password || u.port) return null;   // default port only
    return ALLOWED_CHECKOUT_HOSTS.includes(u.hostname) ? u.toString() : null;
  } catch {
    return null;
  }
}

/** A fresh, URL-safe idempotency key (8 to 64 of A-Za-z0-9_-). Reused on retry of the same click so a retry never creates a second session. */
export function newIdempotencyKey(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return "ck-" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
