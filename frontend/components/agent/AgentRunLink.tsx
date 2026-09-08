import Link from "next/link";

/** Secondary link from the Coach to the safe Agent Inspector for this run. */
export function AgentRunLink({ runId }: { runId: string }) {
  return (
    <Link
      href={`/review/agent?run=${encodeURIComponent(runId)}`}
      className="text-xs font-medium text-muted underline hover:text-foreground"
    >
      View run details
    </Link>
  );
}
