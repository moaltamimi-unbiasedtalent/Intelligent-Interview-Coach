"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { LegalPage } from "@/components/marketing/LegalPage";

// P10B-W9.6: localized body for the Terms page. Extracted from app/terms/page.tsx so it can use
// useT(); the server page keeps its `export const metadata`. Engineering-draft copy, pending legal
// review (meaning preserved; see lib/i18n/messages/w96/legal.ts).
export function TermsContent() {
  const t = useT();
  return (
    <LegalPage title={t("terms.pageTitle")} updated="2026-09-26">
      <p>{t("terms.intro")}</p>

      <h2>{t("terms.whatHeading")}</h2>
      <p>{t("terms.whatBody")}</p>

      <h2>{t("terms.aiHeading")}</h2>
      <ul>
        <li>{t("terms.aiWrong")}</li>
        <li>{t("terms.aiSources")}</li>
        <li>{t("terms.aiScores")}</li>
        <li>{t("terms.aiNoHiring")}</li>
      </ul>

      <h2>{t("terms.respHeading")}</h2>
      <ul>
        <li>{t("terms.respAccurate")}</li>
        <li>{t("terms.respUpload")}</li>
        <li>{t("terms.respLawful")}</li>
      </ul>

      <h2>{t("terms.accountsHeading")}</h2>
      <ul>
        <li>{t("terms.accountsPlans")}</li>
        <li>{t("terms.accountsProviders")}</li>
        <li>{t("terms.accountsAsIs")}</li>
      </ul>

      <h2>{t("terms.changesHeading")}</h2>
      <p>{t("terms.changesBody")}</p>
    </LegalPage>
  );
}
