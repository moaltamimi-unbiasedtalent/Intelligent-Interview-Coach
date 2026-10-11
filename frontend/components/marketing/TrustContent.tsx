"use client";

import Image from "next/image";
import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";
import { MarketingIcon, type IconName } from "@/components/marketing/MarketingIcon";

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
      // "Private by default" is a visible principle card above and is not repeated here (one visible occurrence).
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

const GROUP_ICONS: Record<string, IconName> = { ai: "search", control: "check", data: "shield", voice: "mic" };
const PRINCIPLES: Array<[IconName, string, string]> = [
  ["search", "trust.sourcesTerm", "trust.sourcesDesc"],
  ["check", "trust.suggestionsTerm", "trust.suggestionsDesc"],
  ["shield", "trust.privateTerm", "trust.privateDesc"],
  ["mic", "trust.noAudioTerm", "trust.noAudioDesc"],
  ["shield", "trust.oppPrivateTerm", "trust.oppPrivateDesc"],
];

export function TrustContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-12 md:py-16">
      <section className="relative min-h-[34rem] overflow-hidden rounded-[2rem] bg-black text-white shadow-soft md:min-h-[42rem]" aria-labelledby="trust-page-title">
        <figure className="absolute inset-0">
          <Image
            src="/images/ask4mo/ask4mo-trust-private-evidence-photo.png"
            alt={t("trust.imageAlt")}
            fill
            priority
            sizes="(max-width: 1024px) 100vw, 600px"
            className="object-cover object-center opacity-60"
          />
          <span aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-black via-black/45 to-black/10" />
        </figure>
        <div className="absolute inset-x-0 bottom-0 z-10 p-8 md:p-14">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/65">{t("marketing.trustTitle")}</p>
          <h1 id="trust-page-title" className="mt-3 max-w-4xl text-5xl font-bold tracking-tight md:text-7xl">{t("trust.privateTerm")}.</h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-white/75">{t("marketing.trustSubtitle")}</p>
        </div>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-2" aria-label={t("marketing.trustTitle")}>
        {PRINCIPLES.map(([icon, termKey, descKey], index) => (
          <article key={termKey} className={index === 0 ? "min-h-64 rounded-[1.75rem] bg-[#183f42] p-7 text-white shadow-sm md:p-9" : index === 1 ? "min-h-64 rounded-[1.75rem] bg-[#e9e2f0] p-7 text-[#173f42] md:p-9" : index === 2 ? "min-h-64 rounded-[1.75rem] bg-[#f4cdb9] p-7 text-[#173f42] md:p-9" : "min-h-64 rounded-[1.75rem] border border-border bg-surface p-7 shadow-sm md:p-9" + (index === 4 ? " md:col-span-2 md:min-h-0" : "")}>
            <span className={index === 0 ? "grid h-12 w-12 place-items-center rounded-full bg-white/10 text-[#a9d7cd]" : "grid h-12 w-12 place-items-center rounded-full bg-white/70 text-[#173f42]"}>
              <MarketingIcon name={icon} className="h-5 w-5" />
            </span>
            <h2 className="mt-8 text-2xl font-bold md:text-3xl">{t(termKey)}</h2>
            <p className={index === 0 ? "mt-3 max-w-xl text-sm leading-relaxed text-white/70" : index === 1 || index === 2 ? "mt-3 max-w-xl text-sm leading-relaxed text-[#43595a]" : "mt-3 max-w-xl text-sm leading-relaxed text-muted"}>{t(descKey)}</p>
          </article>
        ))}
      </section>

      <div className="mx-auto mt-20 max-w-4xl">
        <div className="text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Ask4Mo</p>
          <h2 className="mt-3 text-3xl font-bold md:text-5xl">{t("marketing.trustSubtitle")}</h2>
          <p className="mx-auto mt-4 max-w-2xl text-muted">{t("trustUx.limitsDesc")}</p>
        </div>
        <div className="mt-8 space-y-4">
        {GROUPS.map((g) => (
          <details key={g.id} className="group overflow-hidden rounded-[1.5rem] border border-border bg-surface shadow-sm" data-testid={`trust-group-${g.id}`}>
            <summary className="flex cursor-pointer list-none items-center gap-4 px-5 py-5 marker:hidden md:px-7">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-surface-2 text-accent">
                <MarketingIcon name={GROUP_ICONS[g.id]} className="h-5 w-5" />
              </span>
              <h2 id={`trust-${g.id}`} className="flex-1 text-lg font-semibold">{t(g.titleKey)}</h2>
              <span className="text-sm text-muted">{g.controls.length + (g.limits ? 1 : 0)}</span>
              <span aria-hidden="true" className="text-xl text-accent transition group-open:rotate-45 motion-reduce:transition-none">+</span>
            </summary>
            <dl className="grid gap-px border-t border-border bg-border sm:grid-cols-2">
                {g.limits ? (
                  <div className="bg-surface-2 p-5 md:p-6">
                    <dt className="font-semibold">{t("trustUx.limitsTitle")}</dt>
                    <dd className="mt-2 text-sm leading-relaxed text-muted">{t("trustUx.limitsDesc")}</dd>
                  </div>
                ) : null}
                {g.controls.map(([termKey, descKey]) => (
                  <div key={termKey} className="bg-surface p-5 md:p-6">
                    <dt className="font-semibold">{t(termKey)}</dt>
                    <dd className="mt-2 text-sm leading-relaxed text-muted">{t(descKey)}</dd>
                  </div>
                ))}
            </dl>
            {g.dataLink ? (
              <p className="border-t border-border px-5 py-4 text-sm md:px-7">
                <Link href="/account/data" aria-label={t("trustUx.yourDataLink")} className="font-medium text-accent underline">{t("trustUx.yourDataLink")}</Link>
              </p>
            ) : null}
          </details>
        ))}
        </div>
      </div>
      <p className="mx-auto mt-8 max-w-4xl text-sm text-muted">
        {t("trust.moreDetail")}: <Link href="/privacy" className="underline">{t("marketing.footerPrivacy")}</Link>,{" "}
        <Link href="/ai-transparency" className="underline">{t("marketing.footerAi")}</Link>,{" "}
        <Link href="/terms" className="underline">{t("marketing.footerTerms")}</Link>.
      </p>
    </div>
  );
}
