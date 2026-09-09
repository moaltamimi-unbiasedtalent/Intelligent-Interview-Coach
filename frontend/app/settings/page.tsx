import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Card, CardBody } from "@/components/ui/Card";
import { MemoryManager } from "@/components/memory/MemoryManager";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <section className="max-w-reading">
      <PageHeader eyebrow="Account" title="Settings" />
      <div className="grid gap-4">
        <Card>
          <CardBody>
            <h2 className="text-base font-semibold">Appearance</h2>
            <p className="mt-1 text-sm text-muted">
              The interface follows your system light/dark preference; the header toggle
              overrides it and is remembered on this device.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <MemoryManager />
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-base font-semibold">Your data</h2>
            <p className="mt-1 text-sm text-muted">
              Information you share (a role, a job description, a CV) is used only to
              personalise your preparation. Long-term memory holds only the concise
              preparation details you explicitly approve — never whole conversations,
              job descriptions or CVs — and you control it above.
            </p>
          </CardBody>
        </Card>

        <Alert title="Sign-in is coming">
          Production accounts (single sign-on) are planned for a later phase. Until then,
          preparation runs without an account in development.
        </Alert>
      </div>
    </section>
  );
}
