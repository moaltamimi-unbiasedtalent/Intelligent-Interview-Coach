"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { MemoryManager } from "@/components/memory/MemoryManager";
import { ResponseDetailPreference } from "@/components/settings/ResponseDetailPreference";
import { LanguageSettings } from "@/components/settings/LanguageSettings";
import { PersonalisationSettings } from "@/components/settings/PersonalisationSettings";
import { useT } from "@/components/i18n/I18nProvider";

/** Settings page chrome (P10B Wave 1 — localized via useT). Metadata stays in the server page. */
export function SettingsContent() {
  const t = useT();
  return (
    <section className="max-w-reading">
      <PageHeader eyebrow={t("nav.account")} title={t("settings.title")} />
      <div className="grid gap-4">
        <Card>
          <CardBody>
            <PersonalisationSettings />
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <LanguageSettings />
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <ResponseDetailPreference />
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <MemoryManager />
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h2 className="text-base font-semibold">{t("settings.yourData")}</h2>
            <p className="mt-1 text-sm text-muted">
              {t("settings.yourDataDesc")}{" "}
              <a href="/account/data" className="font-medium text-accent hover:underline">
                {t("settings.yourDataManage")}
              </a>
              .
            </p>
          </CardBody>
        </Card>
      </div>
    </section>
  );
}
