import { APP_HOME, AUTH_ONLY_ROUTES } from "./routes";

/** Validate untrusted post-authentication destinations before any navigation. */
export function returnDestination(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return APP_HOME;
  let decoded = value;
  try {
    // Reject ambiguous separators and controls at every encoding layer, while
    // allowing ordinary encoded query values and fragments.
    for (let i = 0; i < 5; i++) {
      if (/[\\\u0000-\u001f\u007f]/.test(decoded)) return APP_HOME;
      const path = decoded.split(/[?#]/, 1)[0];
      if (path.startsWith("//") || /%(?:2f|5c)/i.test(path)) return APP_HOME;
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      if (i === 4) return APP_HOME;
      decoded = next;
    }
    const path = decoded.split(/[?#]/, 1)[0];
    if (path.split("/").some((part) => part === "." || part === "..")) return APP_HOME;
    const url = new URL(value, "https://return.invalid");
    if (url.origin !== "https://return.invalid" || AUTH_ONLY_ROUTES.has(path.replace(/\/$/, "") || "/")) return APP_HOME;
    return value;
  } catch {
    return APP_HOME;
  }
}
