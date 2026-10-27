import { NextRequest, NextResponse } from "next/server";
import { pagePolicy } from "./lib/security/csp";

export function middleware(request: NextRequest) {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const nonce = btoa(String.fromCharCode(...bytes));
  const policy = pagePolicy(nonce, process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1");
  const headers = new Headers(request.headers);
  // Always replace untrusted request values. Next reads this CSP during SSR and
  // attaches the nonce to its framework/bootstrap scripts, not arbitrary markup.
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Cache-Control", "private, no-store, max-age=0, must-revalidate");
  return response;
}

export const config = {
  // Include navigations, prefetch/RSC and error routes. Assets retain edge fallback
  // policy and their existing caching; they do not contain nonce-bearing HTML.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|images/|brand/|fonts/).*)"],
};
