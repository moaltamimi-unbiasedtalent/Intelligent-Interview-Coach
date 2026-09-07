import Link from "next/link";

/** Typographic wordmark with a small neutral conceptual mark (not a final logo). */
export function Brand() {
  return (
    <Link
      href="/"
      className="inline-flex items-center gap-2.5 font-bold tracking-tight text-foreground"
      aria-label="Intelligent Interview Coach — home"
    >
      <span
        aria-hidden="true"
        className="h-4 w-4 rounded-[5px] bg-accent"
        style={{ boxShadow: "inset 0 0 0 3px color-mix(in srgb, var(--accent) 55%, #fff)" }}
      />
      <span>Intelligent Interview Coach</span>
    </Link>
  );
}
