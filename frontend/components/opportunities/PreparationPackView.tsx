"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import type { PackCategory, PackContent, PackItem, PackSection } from "@/lib/api/types";

/**
 * Renders a stored Preparation Pack (W12.4D-P5-A). Presentation only: every label comes from the server-provided category and codes, the viewer decides
 * nothing about access and computes nothing. Each item shows WHERE it comes from in words plus a non-colour marker (never colour alone), AI-assisted guidance
 * is always labelled as not a verified fact, and sources keep their retrieval and publication provenance. Unknown codes degrade to a readable fallback.
 */
const MARK: Record<PackCategory, string> = { candidate_provided: "●", opportunity_provided: "◆", verified_external: "✓", knowledge_base: "▣", ai_guidance: "✦", unavailable: "○" };
const humanize = (s: string) => s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

export function PreparationPackView({ content }: { content: PackContent }) {
  const { t, formatDate } = useI18n();
  const label = (prefix: string, code: string) => {
    const k = `packUx.${prefix}${code}`;
    const v = t(k);
    return v === k ? humanize(code) : v;
  };
  const kindLabel = (kind: string) => {
    const k = `packUx.k_${kind}`;
    const v = t(k);
    return v === k ? null : v;
  };
  const sources = new Map(content.sources.map((s) => [s.id, s]));

  const itemBody = (sec: PackSection, it: PackItem) => {
    if (it.kind === "missing") return `${t("packUx.missingPrefix")} ${label("miss_", it.text)}`;
    if (it.kind === "limitation") return it.text;
    if (it.kind === "alignment") return it.text;
    if (it.kind === "evidence_gap" || it.kind === "information_gap" || it.kind === "preparation_gap") {
      return it.kind === "evidence_gap" ? it.text : label("miss_", it.text);
    }
    return it.text;
  };

  return (
    <div className="space-y-4" data-testid="pack-view">
      <Card>
        <CardBody className="space-y-2">
          <h3 className="text-sm font-semibold text-foreground">{t("packUx.legend")}</h3>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" data-testid="pack-legend">
            {(Object.keys(MARK) as PackCategory[]).map((c) => <li key={c}><span aria-hidden="true">{MARK[c]}</span> {t(`packUx.cat_${c}`)}</li>)}
          </ul>
        </CardBody>
      </Card>
      {content.sections.map((sec) => (
        <Card key={sec.id}>
          <CardBody className="space-y-3">
            <section aria-labelledby={`pack-sec-${sec.id}`} data-testid={`pack-section-${sec.id}`} data-status={sec.status}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 id={`pack-sec-${sec.id}`} className="text-base font-semibold text-foreground">{t(`packUx.sec_${sec.id}`)}</h3>
                <span className="rounded-full border border-border px-2.5 py-0.5 text-xs font-medium text-foreground">{t(`packUx.ss_${sec.status}`)}</span>
              </div>
              {sec.id !== "sources" ? (
                <ul className="mt-2 space-y-2">
                  {sec.items.map((it, i) => (
                    <li key={`${sec.id}-${i}`} className="rounded-lg border border-border bg-surface p-3 text-sm" data-category={it.category} data-kind={it.kind}>
                      <p className="text-xs text-muted"><span aria-hidden="true">{MARK[it.category]}</span> {t(`packUx.cat_${it.category}`)}
                        {kindLabel(it.kind) ? ` · ${kindLabel(it.kind)}` : ""}</p>
                      <p className="mt-1 text-foreground">{itemBody(sec, it)}</p>
                      {it.kind === "alignment" && it.meta.status ? <p className="mt-1 text-xs font-medium text-foreground">{label("al_", it.meta.status)}</p> : null}
                      {it.meta.detail ? <p className="mt-1 text-xs text-muted">{label("detail_", it.meta.detail)}</p> : null}
                      {it.meta.question_type ? <p className="mt-1 text-xs text-muted">{label("qk_", it.meta.question_type)}</p> : null}
                      {it.meta.evidence_to_prepare ? <p className="mt-1 text-xs text-muted">{t("packUx.evidenceToPrepare")}: {it.meta.evidence_to_prepare}</p> : null}
                      {it.meta.follow_ups ? <p className="mt-1 text-xs text-muted">{t("packUx.followUps")}: {it.meta.follow_ups}</p> : null}
                      {it.meta.action_type ? <p className="mt-1 text-xs font-medium text-foreground">{it.meta.order}. {label("a_", it.meta.action_type)}</p> : null}
                      {it.source_ids.length ? (
                        <p className="mt-1 text-xs text-muted">{it.source_ids.map((id) => sources.get(id)?.title ?? id).join("; ")}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="mt-2 space-y-4">
                  {content.sources.length ? (
                    <div>
                      <h4 className="text-sm font-semibold text-foreground">{t("packUx.sourcesTitle")}</h4>
                      <ul className="mt-1 space-y-2 text-sm" data-testid="pack-sources">
                        {content.sources.map((s) => (
                          <li key={s.id} className="rounded-lg border border-border bg-surface p-3">
                            <p className="text-xs text-muted"><span aria-hidden="true">{MARK[s.category]}</span> {t(`packUx.cat_${s.category}`)}{s.self_reported ? ` · ${t("packUx.selfReported")}` : ""}</p>
                            <p className="mt-1 text-foreground">{s.title}</p>
                            <p className="mt-1 text-xs text-muted">
                              {s.retrieved_at ? `${t("packUx.retrieved")}: ${formatDate(s.retrieved_at, { dateStyle: "medium" })}` : ""}
                              {s.effective_date ? ` · ${t("packUx.published")}: ${formatDate(s.effective_date, { dateStyle: "medium" })}` : ""}
                            </p>
                            {s.url && /^https?:\/\//i.test(s.url) ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block break-all text-xs text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("packUx.openSource")}: {s.url}</a> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <div><h4 className="text-sm font-semibold text-foreground">{t("packUx.assumptionsTitle")}</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted">{content.assumptions.map((a) => <li key={a}>{label("as_", a)}</li>)}</ul></div>
                  <div><h4 className="text-sm font-semibold text-foreground">{t("packUx.limitationsTitle")}</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted" data-testid="pack-limitations">{content.limitations.map((a) => <li key={a}>{label("lim_", a)}</li>)}</ul></div>
                </div>
              )}
              {sec.notes.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted" aria-label={t("packUx.notesTitle")}>{sec.notes.map((n) => <li key={n}>{label("note_", n)}</li>)}</ul>
              ) : null}
            </section>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
