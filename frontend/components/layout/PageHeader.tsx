import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-reading">
        {eyebrow ? (
          <p className="text-sm font-semibold text-accent">{eyebrow}</p>
        ) : null}
        <h1 className="mt-1 text-2xl md:text-3xl">{title}</h1>
        {description ? (
          <p className="mt-2 text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}
