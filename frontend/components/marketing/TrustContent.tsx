"use client";

import Image from "next/image";
import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";

// Trust surface (Capstone P8 §9). Factual engineering controls, stated plainly. No certification
// badges. P10B-W9.6: the control statements are localized via the `trust` namespace (term + desc
// key pair per control); engineering-draft copy, meaning preserved (see w96/legal.ts).
type Control = [string, string];

// Controls are grouped so a reader can find "what AI does", "what I control", "what happens to my data"
// and "voice/providers" without scanning one flat list. Every control is an implemented behaviour.
const GROUPS: Array<{ id: string; titleKey: string; controls: Control[]; limits?: boolean; dataLink?: boolean }> = [
  {
    id: "ai",
    titleKey: "trustUx.groupAi",
    limits: true,
    controls: [
      ["trust.sourcesTerm", "trust.sourcesDesc"],
      ["trust.factsSeparateTerm", "trust.factsSeparateDesc"],
      ["trust.suggestionsTerm", "trust.suggestionsDesc"],
      ["trust.evidenceGovernedTerm", "trust.evidenceGovernedDesc"],
      ["trust.boundedAgentsTerm", "trust.boundedAgentsDesc"],
      ["trust.noHiringTerm", "trust.noHiringDesc"],
    ],
  },
  {
    id: "control",
    titleKey: "trustUx.groupControl",
    controls: [
      ["trust.approvalsTerm", "trust.approvalsDesc"],
      ["trust.layeredContextTerm", "trust.layeredContextDesc"],
      ["trust.languageMarketTerm", "trust.languageMarketDesc"],
    ],
  },
  {
    id: "data",
    titleKey: "trustUx.groupData",
    dataLink: true,
    controls: [
      ["trust.isolationTerm", "trust.isolationDesc"],
      ["trust.privateTerm", "trust.privateDesc"],
      ["trust.oppPrivateTerm", "trust.oppPrivateDesc"],
      ["trust.workspaceShareTerm", "trust.workspaceShareDesc"],
      ["trust.exportDeleteTerm", "trust.exportDeleteDesc"],
    ],
  },
  {
    id: "voice",
    titleKey: "trustUx.groupVoice",
    controls: [
      ["trust.noVoiceTraitTerm", "trust.noVoiceTraitDesc"],
      ["trust.noAudioTerm", "trust.noAudioDesc"],
      ["trust.providerBoundariesTerm", "trust.providerBoundariesDesc"],
    ],
  },
];

export function TrustContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-reading px-4 py-16">
      <h1 className="text-3xl font-bold md:text-4xl">{t("marketing.trustTitle")}</h1>
      <p className="mt-3 text-muted">{t("marketing.trustSubtitle")}</p>
      {/* Wave 8 B0: privacy/evidence still life. Shown full (no crop) so both hands, the folio and
          the source card remain visible; photograph uses the border radius + border token. */}
      <figure className="mt-6 overflow-hidden rounded-lg border border-border">
        <Image
          src="/images/ask4mo/ask4mo-trust-private-evidence-photo.png"
          alt={t("trust.imageAlt")}
          width={1448}
          height={1086}
          sizes="(max-width: 720px) 100vw, 720px"
          className="h-auto w-full"
        />
      </figure>
      <div className="mt-10 space-y-10">
        {GROUPS.map((g) => (
          <section key={g.id} aria-labelledby={`trust-${g.id}`} data-testid={`trust-group-${g.id}`}>
            <h2 id={`trust-${g.id}`} className="text-xl font-semibold">{t(g.titleKey)}</h2>
            <dl className="mt-3 divide-y divide-border rounded-lg border border-border bg-surface">
              {g.limits ? (
                <div className="p-4">
                  <dt className="font-semibold">{t("trustUx.limitsTitle")}</dt>
                  <dd className="mt-1 text-sm text-muted">{t("trustUx.limitsDesc")}</dd>
                </div>
              ) : null}
              {g.controls.map(([termKey, descKey]) => (
                <div key={termKey} className="p-4">
                  <dt className="font-semibold">{t(termKey)}</dt>
                  <dd className="mt-1 text-sm text-muted">{t(descKey)}</dd>
                </div>
              ))}
            </dl>
            {g.dataLink ? (
              <p className="mt-3 text-sm">
                <Link href="/account/data" className="font-medium text-accent underline">{t("trustUx.yourDataLink")}</Link>
              </p>
            ) : null}
          </section>
        ))}
      </div>
      <p className="mt-8 text-sm text-muted">
        {t("trust.moreDetail")}: <Link href="/privacy" className="underline">{t("marketing.footerPrivacy")}</Link>,{" "}
        <Link href="/ai-transparency" className="underline">{t("marketing.footerAi")}</Link>,{" "}
        <Link href="/terms" className="underline">{t("marketing.footerTerms")}</Link>.
      </p>
    </div>
  );
}
