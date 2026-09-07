import { cn } from "@/lib/utils";

/** Question progress dots + count. Purely visual in Phase 3B. */
export function InterviewProgress({ total, current }: { total: number; current: number }) {
  return (
    <div className="text-center">
      <div className="flex justify-center gap-1.5" aria-hidden="true">
        {Array.from({ length: total }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-1.5 w-8 rounded-full",
              i < current - 1
                ? "bg-accent"
                : i === current - 1
                  ? "bg-secondary"
                  : "bg-surface-2",
            )}
          />
        ))}
      </div>
      <p className="mt-2 text-sm text-muted">
        Question {current} of {total}
      </p>
    </div>
  );
}
