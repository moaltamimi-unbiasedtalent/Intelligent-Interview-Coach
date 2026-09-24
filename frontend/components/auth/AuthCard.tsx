import type { ReactNode } from "react";
import { Card, CardBody } from "@/components/ui/Card";

/** Centred card used by all auth pages, in the Ask4Mo design language. */
export function AuthCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-[440px] py-6">
      <Card>
        <CardBody className="space-y-5">
          <div className="space-y-1">
            <h1 className="text-xl font-bold text-foreground">{title}</h1>
            {subtitle ? <p className="text-sm text-muted">{subtitle}</p> : null}
          </div>
          {children}
        </CardBody>
      </Card>
      {footer ? <div className="mt-4 text-center text-sm text-muted">{footer}</div> : null}
    </div>
  );
}

/** A labelled field row. */
export function LabelledField({
  label,
  htmlFor,
  children,
  hint,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-foreground">
        {label}
      </label>
      {children}
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
