/** Quiet, expandable evidence line. Candidate-friendly language ("evidence"). */
export function SourceList({
  summary,
  detail,
}: {
  summary: string;
  detail?: string;
}) {
  return (
    <p className="text-sm text-muted">
      <span className="mr-1">Career evidence:</span>
      {detail ? (
        <details className="inline">
          <summary className="inline cursor-pointer text-foreground">{summary}</summary>
          <span className="ml-1 block pt-1 text-muted">{detail}</span>
        </details>
      ) : (
        <span className="text-foreground">{summary}</span>
      )}
    </p>
  );
}
