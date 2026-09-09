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
      <span
        aria-hidden="true"
        className="h-4 w-4 rounded-[5px] bg-accent"
        style={{ boxShadow: "inset 0 0 0 3px color-mix(in srgb, var(--accent) 55%, #fff)" }}
      />
      <span>Ask4Mo</span>
    </Link>
  );
}
