import Link from "next/link";

/**
 * Ask4Mo wordmark with a small "Conversation Bridge" mark (a placeholder for the final
 * vector logo — see /public/brand/ask4mo-mark.svg when supplied). The compact header
 * shows only "Ask4Mo"; the full lockup (descriptor + slogan) lives on Home (§3/§32).
 */
export function Brand() {
  return (
    <Link
      href="/"
      className="inline-flex items-center gap-2.5 font-bold tracking-tight text-foreground"
      aria-label="Ask4Mo — home"
    >
      {/* Conversation Bridge mark (placeholder asset). Decorative — the link's
          aria-label carries the accessible name; the text wordmark is the fallback. A
          plain <img> is intentional for this tiny static SVG icon (no optimisation
          benefit from next/image). */}
      {/* ~1.5× larger for presence (28px mobile → 30px desktop, up from 20px). */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/brand/ask4mo-mark.svg" alt="" aria-hidden="true" width={30} height={30} className="h-7 w-7 sm:h-[30px] sm:w-[30px]" />
      <span>Ask4Mo</span>
    </Link>
  );
}
