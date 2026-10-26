/** Page policy shared by rendering and the response; never derived from client headers. */
export function pagePolicy(nonce: string, apiBase: string): string {
  if (!/^[A-Za-z0-9+/]{43}=$/.test(nonce)) throw new Error("Invalid CSP nonce");
  const api = new URL(apiBase);
  if ((!/^[a-z0-9.-]+$/i.test(api.hostname) && api.hostname !== "[::1]") ||
      api.username || api.password || api.search || api.hash ||
      (api.protocol !== "https:" && !(api.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(api.hostname)))) {
    throw new Error("Invalid public API origin");
  }
  const websocket = new URL(api.origin);
  websocket.protocol = api.protocol === "https:" ? "wss:" : "ws:";
  return [
    "default-src 'self'", "base-uri 'self'", "frame-ancestors 'none'", "object-src 'none'",
    "img-src 'self' data: blob:", "style-src 'self' 'unsafe-inline'",
    `script-src 'self' 'nonce-${nonce}'`, "script-src-attr 'none'", "font-src 'self' data:",
    `connect-src 'self' ${api.origin} ${websocket.origin}`,
    "media-src 'self' blob:", "form-action 'self'",
  ].join("; ");
}
