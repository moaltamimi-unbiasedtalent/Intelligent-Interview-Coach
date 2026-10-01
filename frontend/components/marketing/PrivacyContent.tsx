"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { LegalPage } from "@/components/marketing/LegalPage";

// P10B-W9.6: localized body for the Privacy page. Extracted from the server page (app/privacy/page.tsx)
// so it can use useT(); the server page keeps its `export const metadata`. Engineering-draft copy,
// pending legal review (meaning preserved; see lib/i18n/messages/w96/legal.ts).
export function PrivacyContent() {
  const t = useT();
  return (
    <LegalPage title={t("privacy.pageTitle")} updated="2026-09-26">
      <p>{t("privacy.intro")}</p>

      <h2>{t("privacy.storeHeading")}</h2>
      <ul>
        <li><strong>{t("privacy.storeAccountTerm")}</strong>: {t("privacy.storeAccountDesc")}</li>
        <li><strong>{t("privacy.storePrepTerm")}</strong>: {t("privacy.storePrepDesc")}</li>
        <li><strong>{t("privacy.storeDocsTerm")}</strong>: {t("privacy.storeDocsDesc")}</li>
        <li><strong>{t("privacy.storePracticeTerm")}</strong>: {t("privacy.storePracticeDesc")}</li>
        <li><strong>{t("privacy.storeMemoryTerm")}</strong>: {t("privacy.storeMemoryDesc")}</li>
        <li><strong>{t("privacy.storeStoryTerm")}</strong>: {t("privacy.storeStoryDesc")}</li>
        <li><strong>{t("privacy.storeWorkspacesTerm")}</strong>: {t("privacy.storeWorkspacesDesc")}</li>
        <li><strong>{t("privacy.storeFeedbackTerm")}</strong>: {t("privacy.storeFeedbackDesc")}</li>
        <li><strong>{t("privacy.storeMetadataTerm")}</strong>: {t("privacy.storeMetadataDesc")}</li>
      </ul>

      <h2>{t("privacy.voiceHeading")}</h2>
      <ul>
        <li>{t("privacy.voiceTurnBased")}</li>
        <li>{t("privacy.voiceRealtime")}</li>
        <li>{t("privacy.voiceNoInference")}</li>
      </ul>

      <h2>{t("privacy.externalHeading")}</h2>
      <ul>
        <li>{t("privacy.externalAi")}</li>
        <li>{t("privacy.externalResearch")}</li>
        <li>{t("privacy.externalEmail")}</li>
        <li>{t("privacy.externalKeys")}</li>
      </ul>

      <h2>{t("privacy.retentionHeading")}</h2>
      <ul>
        <li>{t("privacy.retentionExport")}</li>
        <li>{t("privacy.retentionAudit")}</li>
        <li>{t("privacy.retentionBackups")}</li>
        <li>{t("privacy.retentionRights")}</li>
      </ul>

      <h2>{t("privacy.contactHeading")}</h2>
      <p>{t("privacy.contactBody")}</p>
    </LegalPage>
  );
}
