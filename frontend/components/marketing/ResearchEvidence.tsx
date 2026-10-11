"use client";

import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";

const GOV_EVALUATION_URL =
  "https://www.gov.uk/government/publications/stem-recharge-programme-evaluation/stem-recharge-programme-evaluation";
const VIDEO_INTERVIEW_STUDY_URL =
  "https://www.sciencedirect.com/science/article/pii/S0001879123000726";

/**
 * Independent research context, deliberately separated from product claims. The compact editorial treatment
 * borrows the trust-building rhythm of modern coaching sites without presenting another company's outcomes as ours.
 */
export function ResearchEvidence() {
  const t = useT();

  return (
    <section className="border-y border-[#d4c7df] bg-[#e9e2f0] text-[#173f42]" aria-labelledby="research-evidence-title">
      <div className="mx-auto max-w-content px-4 py-16 md:py-20">
        <div className="grid gap-10 lg:grid-cols-[0.72fr_1.28fr] lg:items-end">
          <div>
            <p className="inline-flex rounded-full border border-[#725b83]/20 bg-white/65 px-3 py-1.5 text-sm font-semibold uppercase tracking-[0.16em] text-[#6f5687]">
              {t("researchEvidence.eyebrow")}
            </p>
            <h2 id="research-evidence-title" className="mt-3 text-3xl font-bold tracking-tight md:text-5xl">
              {t("researchEvidence.title")}
            </h2>
            <p className="mt-5 max-w-xl leading-relaxed text-[#43595a]">{t("researchEvidence.lead")}</p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <article className="rounded-[1.75rem] bg-[#173f42] p-6 text-white shadow-soft md:-rotate-1 md:p-8">
              <p className="text-4xl font-bold tracking-tight md:text-5xl">36% → 63%</p>
              <h3 className="mt-4 text-lg font-bold">{t("researchEvidence.confidenceTitle")}</h3>
              <p className="mt-3 text-sm leading-relaxed text-white/75">{t("researchEvidence.confidenceBody")}</p>
              <a
                href={GOV_EVALUATION_URL}
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-flex text-sm font-semibold underline decoration-[#f1a886] decoration-2 underline-offset-4"
              >
                {t("researchEvidence.govSource")} ↗
              </a>
            </article>

            <article className="rounded-[1.75rem] bg-[#f4cdb9] p-6 text-[#173f42] shadow-soft md:rotate-1 md:p-8">
              <p className="text-4xl font-bold tracking-tight md:text-5xl">358</p>
              <h3 className="mt-4 text-lg font-bold">{t("researchEvidence.trainingTitle")}</h3>
              <p className="mt-3 text-sm leading-relaxed text-[#39595a]">{t("researchEvidence.trainingBody")}</p>
              <a
                href={VIDEO_INTERVIEW_STUDY_URL}
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-flex text-sm font-semibold underline decoration-[#d97d5c] decoration-2 underline-offset-4"
              >
                {t("researchEvidence.studySource")} ↗
              </a>
            </article>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-4 border-t border-[#173f42]/15 pt-6 text-sm text-[#43595a] md:flex-row md:items-center md:justify-between">
          <p className="max-w-3xl">{t("researchEvidence.caveat")}</p>
          <Link href="/product#how-it-works" className="shrink-0 font-semibold text-[#173f42] underline decoration-[#d96f4e] decoration-2 underline-offset-4">
            {t("researchEvidence.cta")} →
          </Link>
        </div>
      </div>
    </section>
  );
}
