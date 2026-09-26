import { Logo } from "@/components/ui/Logo";
import { APP_HOME } from "@/lib/auth/routes";

/**
 * App-header brand: the canonical Ask4Mo logo (P10B Wave 1 — one shared implementation via
 * `Logo`). Inside the authenticated product the wordmark links to the app home (`/app`); the
 * public marketing chrome links its own logo to `/`.
 */
export function Brand() {
  return <Logo href={APP_HOME} />;
}
