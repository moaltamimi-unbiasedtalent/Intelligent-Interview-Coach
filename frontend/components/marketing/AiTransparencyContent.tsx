"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { LegalPage } from "@/components/marketing/LegalPage";

// P10B-W9.6: localized body for the AI transparency page. Extracted from app/ai-transparency/page.tsx
// so it can use useT(); the server page keeps its `export const metadata`. Engineering-draft copy,
// pending legal review (meaning preserved; see lib/i18n/messages/w96/legal.ts).
export function AiTransparencyContent() {
  const t = useT();
  return (
    <LegalPage title={t("aiTransparency.pageTitle")} updated="2026-09-26">
      <p>{t("aiTransparency.intro")}</p>

      <h2>{t("aiTransparency.whatMoHeading")}</h2>
      <p>{t("aiTransparency.whatMoBody")}</p>

      <h2>{t("aiTransparency.whenHeading")}</h2>
      <ul>
        <li>{t("aiTransparency.whenAi")}</li>
        <li>{t("aiTransparency.whenDeterministic")}</li>
        <li>{t("aiTransparency.whenPolicy")}</li>
      </ul>

      <h2>{t("aiTransparency.specialistsHeading")}</h2>
      <ul>
        <li>{t("aiTransparency.specialistsBounded")}</li>
        <li>{t("aiTransparency.specialistsGrounded")}</li>
      </ul>

      <h2>{t("aiTransparency.approvalsHeading")}</h2>
      <ul>
        <li>{t("aiTransparency.approvalsMemory")}</li>
        <li>{t("aiTransparency.approvalsFeedback")}</li>
      </ul>

      <h2>{t("aiTransparency.limitsHeading")}</h2>
      <ul>
        <li>{t("aiTransparency.limitsModels")}</li>
        <li>{t("aiTransparency.limitsRealtime")}</li>
      </ul>

      <h2>{t("aiTransparency.neverHeading")}</h2>
      <ul>
        <li>{t("aiTransparency.neverInference")}</li>
        <li>{t("aiTransparency.neverHiring")}</li>
        <li>{t("aiTransparency.neverPrompts")}</li>
      </ul>
    </LegalPage>
  );
}
