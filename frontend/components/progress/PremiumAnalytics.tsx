"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { api } from "@/lib/api/client";
import type { AnalyticsCompareResponse, AnalyticsOverviewResponse, AnalyticsPoint } from "@/lib/api/types";

/**
 * Premium progress analytics and attempt comparison (W12.4D-P4-B) over the SERVER's measurements (GET /progress/analytics). The component computes nothing about
 * authorization and nothing about scores beyond layout: while the server answers feature_disabled or not_entitled (or the request fails) it renders `fallback`
 * (the existing truthful planned-trends notice), so a Basic or disabled account never sees a chart, a number, a link or a purchase prompt. No sample data exists.
 * Every chart has a text alternative (the table), no meaning rests on colour alone, and nothing here claims prediction, causation or a hiring signal.
 */
const DIMS: Record<string, string> = {
  relevance: "analyticsUx.dimRelevance", structure: "analyticsUx.dimStructure", evidence: "analyticsUx.dimEvidence", role_knowledge: "analyticsUx.dimRoleKnowledge",
  problem_solving: "analyticsUx.dimProblemSolving", communication: "analyticsUx.dimCommunication", credibility: "analyticsUx.dimCredibility",
};
const REASONS: Record<string, string> = {
  different_role: "analyticsUx.rDifferentRole", different_level: "analyticsUx.rDifferentLevel", different_opportunity: "analyticsUx.rDifferentOpportunity",
  different_question_mix: "analyticsUx.rDifferentQuestionMix", different_question_count: "analyticsUx.rDifferentQuestionCount", low_sample: "analyticsUx.rLowSample",
};
const DIRECTION: Record<string, string> = { improved: "analyticsUx.dirImproved", declined: "analyticsUx.dirDeclined", unchanged: "analyticsUx.dirUnchanged" };
const ARROW: Record<string, string> = { improved: "▲", declined: "▼", unchanged: "■" };
const humanize = (s: string) => s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function TrendChart({ points, label }: { points: AnalyticsPoint[]; label: string }) {
  const scored = points.filter((p) => p.practice_score !== null);
  const W = 560, H = 200, L = 34, R = 12, T = 12, B = 24;
  const x = (i: number) => (scored.length === 1 ? (L + W - R) / 2 : L + (i * (W - L - R)) / (scored.length - 1));
  const y = (v: number) => T + ((100 - v) * (H - T - B)) / 100;
  const path = scored.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.practice_score as number).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="h-auto w-full max-w-full" data-testid="analytics-chart">
      {[0, 50, 100].map((g) => (
        <g key={g}>
          <line x1={L} x2={W - R} y1={y(g)} y2={y(g)} stroke="currentColor" strokeOpacity="0.2" />
          <text x={L - 6} y={y(g) + 4} textAnchor="end" fontSize="11" fill="currentColor">{g}</text>
        </g>
      ))}
      {scored.length > 1 ? <path d={path} fill="none" stroke="currentColor" strokeWidth="2" /> : null}
      {scored.map((p, i) => (
        <g key={p.interview_id}>
          <rect x={x(i) - 4} y={y(p.practice_score as number) - 4} width="8" height="8" fill="currentColor" transform={`rotate(45 ${x(i)} ${y(p.practice_score as number)})`}>
            <title>{`${p.date ? p.date.slice(0, 10) : ""} · ${p.practice_score}`}</title>
          </rect>
        </g>
      ))}
    </svg>
  );
}

export function PremiumAnalytics({ fallback }: { fallback: ReactNode }) {
  const { t, formatDate, formatNumber } = useI18n();
  const [opportunity, setOpportunity] = useState<number | null>(null);
  const [data, setData] = useState<AnalyticsOverviewResponse | null>(null);
  const [base, setBase] = useState("");
  const [target, setTarget] = useState("");
  const [cmp, setCmp] = useState<AnalyticsCompareResponse | null>(null);
  const [cmpFailed, setCmpFailed] = useState(false);

  useEffect(() => {
    let live = true;
    Promise.resolve().then(() => api.progressAnalytics.get(opportunity)).then((r) => { if (live && r && typeof r.state === "string") setData(r); }).catch(() => { if (live) setData(null); });
    return () => { live = false; };
  }, [opportunity]);

  useEffect(() => {
    setCmp(null);
    setCmpFailed(false);
    if (!base || !target || base === target) return;
    let live = true;
    Promise.resolve().then(() => api.progressAnalytics.compare(Number(base), Number(target))).then((r) => { if (live) setCmp(r); }).catch(() => { if (live) setCmpFailed(true); });
    return () => { live = false; };
  }, [base, target]);

  const scored = useMemo(() => (data?.points ?? []).filter((p) => p.practice_score !== null), [data]);
  if (!data || !["no_data", "insufficient_data", "ready"].includes(data.state)) return <>{fallback}</>;

  const date = (d: string | null) => (d ? formatDate(d, { dateStyle: "medium" }) : "");
  const num = (v: number | null | undefined) => (typeof v === "number" ? formatNumber(v) : t("analyticsUx.notMeasured"));
  const s = data.summary;
  const chip = (dir: string | null) => (dir && DIRECTION[dir] ? `${ARROW[dir]} ${t(DIRECTION[dir])}` : null);

  return (
    <section className="mt-6 space-y-4" aria-labelledby="analytics-title" data-testid="premium-analytics" data-state={data.state}>
      <div>
        <h3 id="analytics-title" className="text-sm font-semibold text-foreground">{t("analyticsUx.title")}</h3>
        <p className="mt-1 text-xs text-muted">{t("analyticsUx.lead")}</p>
      </div>
      {data.filters && data.filters.opportunity_ids.length > 0 ? (
        <div>
          <label htmlFor="analytics-opportunity" className="mr-2 text-xs font-medium text-foreground">{t("analyticsUx.filterLabel")}</label>
          <select id="analytics-opportunity" className="min-h-[44px] rounded border border-border bg-surface px-2 text-sm" value={opportunity ?? ""}
                  onChange={(e) => setOpportunity(e.target.value ? Number(e.target.value) : null)}>
            <option value="">{t("analyticsUx.filterAll")}</option>
            {data.filters.opportunity_ids.map((id) => <option key={id} value={id}>{t("analyticsUx.filterOpportunity", { id })}</option>)}
          </select>
        </div>
      ) : null}
      {data.truncated ? <p className="text-xs text-muted" data-testid="analytics-truncated">{t("analyticsUx.truncated", { n: data.analyzed_limit ?? data.points.length })}</p> : null}

      {data.state === "no_data" ? <p className="text-sm text-muted">{t("analyticsUx.noData")}</p> : (
        <>
          <Card>
            <CardBody className="space-y-3">
              <h4 className="text-sm font-semibold text-foreground">{t("analyticsUx.trendTitle")}</h4>
              {data.state === "insufficient_data" ? <p className="text-sm text-muted" data-testid="analytics-insufficient">{t("analyticsUx.insufficient")}</p> : null}
              {scored.length ? (
                <TrendChart points={data.points} label={t("analyticsUx.chartLabel", { n: scored.length, first: num(scored[0].practice_score), latest: num(scored[scored.length - 1].practice_score) })} />
              ) : null}
              {s && s.latest_score !== null ? (
                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  {([["sumFirst", s.first_score], ["sumLatest", s.latest_score], ["sumAverage", s.average_score], ["sumBest", s.best_score]] as const).map(([k, v]) => (
                    <div key={k}><dt className="text-xs text-muted">{t(`analyticsUx.${k}`)}</dt><dd className="text-lg font-semibold text-foreground">{num(v)}</dd></div>
                  ))}
                  {s.change !== null ? (
                    <div data-testid="analytics-change"><dt className="text-xs text-muted">{t("analyticsUx.sumChange")}</dt>
                      <dd className="text-lg font-semibold text-foreground">{`${s.change > 0 ? "+" : ""}${formatNumber(s.change)}`} <span className="text-sm font-medium">{chip(s.direction)}</span></dd></div>
                  ) : null}
                </dl>
              ) : null}
              {s && s.change !== null ? <p className="text-xs text-muted">{s.comparable_context ? t("analyticsUx.contextSame") : t("analyticsUx.contextDiffers")}</p> : null}
              <div className="overflow-x-auto">
                <table className="w-full min-w-[320px] text-left text-sm" data-testid="analytics-table">
                  <caption className="sr-only">{t("analyticsUx.tableCaption")}</caption>
                  <thead><tr className="text-xs text-muted">
                    <th scope="col" className="py-1 pr-3 font-medium">{t("analyticsUx.colDate")}</th><th scope="col" className="py-1 pr-3 font-medium">{t("analyticsUx.colScore")}</th>
                    <th scope="col" className="py-1 pr-3 font-medium">{t("analyticsUx.colAnswers")}</th><th scope="col" className="py-1 font-medium">{t("analyticsUx.colReport")}</th></tr></thead>
                  <tbody>
                    {data.points.map((p) => (
                      <tr key={p.interview_id} className="border-t border-border">
                        <td className="py-1 pr-3">{date(p.date)}</td>
                        <td className="py-1 pr-3">{num(p.practice_score)}{p.low_sample ? <span className="ml-2 text-xs text-muted">{t("analyticsUx.lowSample")}</span> : null}</td>
                        <td className="py-1 pr-3">{formatNumber(p.answers_scored)}</td><td className="py-1">{num(p.report_score)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>

          {data.rubric && data.rubric.dimensions.some((d) => d.average !== null) ? (
            <Card>
              <CardBody className="space-y-3" data-testid="analytics-rubric">
                <h4 className="text-sm font-semibold text-foreground">{t("analyticsUx.rubricTitle")}</h4>
                <p className="text-xs text-muted">{t("analyticsUx.rubricNote")}</p>
                <ul className="grid gap-2">
                  {data.rubric.dimensions.filter((d) => DIMS[d.id]).map((d) => (
                    <li key={d.id} data-dimension={d.id}>
                      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                        <span className="font-medium text-foreground">{t(DIMS[d.id])}
                          {data.rubric?.strongest === d.id ? <span className="ml-2 text-xs text-muted">▲ {t("analyticsUx.highest")}</span> : null}
                          {data.rubric?.weakest === d.id ? <span className="ml-2 text-xs text-muted">▼ {t("analyticsUx.lowest")}</span> : null}
                        </span>
                        <span>{num(d.average)} / 10 <span className="text-xs text-muted">({t("analyticsUx.answersCount", { n: d.answers_measured })})</span></span>
                      </div>
                      <div className="mt-1 h-2 w-full rounded bg-surface-2" aria-hidden="true"><div className="h-2 rounded bg-foreground/70" style={{ width: `${((d.average ?? 0) / 10) * 100}%` }} /></div>
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            {data.by_question_type.length ? (
              <Card><CardBody>
                <h4 className="mb-2 text-sm font-semibold text-foreground">{t("analyticsUx.typesTitle")}</h4>
                <ul className="space-y-1 text-sm">{data.by_question_type.map((q) => <li key={q.type} className="flex justify-between gap-2"><span>{humanize(q.type)}</span><span>{num(q.average_score)} <span className="text-xs text-muted">({t("analyticsUx.answersCount", { n: q.answers_scored })})</span></span></li>)}</ul>
              </CardBody></Card>
            ) : null}
            {scored.length ? (
              <Card><CardBody>
                <h4 className="mb-2 text-sm font-semibold text-foreground">{t("analyticsUx.distributionTitle")}</h4>
                <ul className="space-y-1 text-sm">{Object.entries(data.distribution).map(([band, n]) => <li key={band} className="flex justify-between gap-2"><span>{band}</span><span>{formatNumber(n)}</span></li>)}</ul>
              </CardBody></Card>
            ) : null}
            {data.frequency ? (
              <Card><CardBody>
                <h4 className="mb-2 text-sm font-semibold text-foreground">{t("analyticsUx.frequencyTitle")}</h4>
                <ul className="space-y-1 text-sm">
                  <li className="flex justify-between gap-2"><span>{t("analyticsUx.freq30")}</span><span>{formatNumber(data.frequency.last_30_days)}</span></li>
                  <li className="flex justify-between gap-2"><span>{t("analyticsUx.freq90")}</span><span>{formatNumber(data.frequency.last_90_days)}</span></li>
                </ul>
              </CardBody></Card>
            ) : null}
            {data.improvement_areas.length ? (
              <Card><CardBody>
                <h4 className="mb-1 text-sm font-semibold text-foreground">{t("analyticsUx.areasTitle")}</h4>
                <p className="mb-2 text-xs text-muted">{t("analyticsUx.areasNote")}</p>
                <ul className="space-y-1 text-sm">{data.improvement_areas.map((a) => <li key={a.area} className="flex justify-between gap-2"><span>{a.area}</span><span>{formatNumber(a.count)}</span></li>)}</ul>
              </CardBody></Card>
            ) : null}
          </div>

          {data.points.length >= 2 ? (
            <Card>
              <CardBody className="space-y-3" data-testid="analytics-compare">
                <h4 className="text-sm font-semibold text-foreground">{t("analyticsUx.compareTitle")}</h4>
                <p className="text-xs text-muted">{t("analyticsUx.compareLead")}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {([["base", t("analyticsUx.compareBase"), base, setBase], ["target", t("analyticsUx.compareTarget"), target, setTarget]] as const).map(([id, label, value, set]) => (
                    <div key={id}>
                      <label htmlFor={`analytics-${id}`} className="mb-1 block text-xs font-medium text-foreground">{label}</label>
                      <select id={`analytics-${id}`} className="min-h-[44px] w-full rounded border border-border bg-surface px-2 text-sm" value={value} onChange={(e) => set(e.target.value)}>
                        <option value="">{t("analyticsUx.comparePick")}</option>
                        {data.points.map((p) => <option key={p.interview_id} value={p.interview_id}>{t("analyticsUx.interviewOption", { id: p.interview_id, date: date(p.date) })}</option>)}
                      </select>
                    </div>
                  ))}
                </div>
                {cmpFailed ? <p role="alert" className="text-sm text-muted">{t("analyticsUx.compareError")}</p> : null}
                {cmp && cmp.state === "insufficient_data" ? <p className="text-sm text-muted">{t("analyticsUx.compareInsufficient")}</p> : null}
                {cmp && cmp.state === "ready" ? (
                  <div className="space-y-3" data-testid="analytics-compare-result">
                    <p className="text-lg font-semibold text-foreground">{t("analyticsUx.compareDiff")}: {`${(cmp.score_difference ?? 0) > 0 ? "+" : ""}${formatNumber(cmp.score_difference ?? 0)}`} <span className="text-sm font-medium">{chip(cmp.direction)}</span></p>
                    <p className="text-sm text-muted" data-comparability={cmp.comparability}>{cmp.comparability === "comparable" ? t("analyticsUx.compareComparable") : t("analyticsUx.compareLimited")}</p>
                    {cmp.comparability_reasons.length ? <ul className="list-disc pl-5 text-sm text-muted">{cmp.comparability_reasons.filter((r) => REASONS[r]).map((r) => <li key={r}>{t(REASONS[r])}</li>)}</ul> : null}
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[320px] text-left text-sm">
                        <thead><tr className="text-xs text-muted"><th scope="col" className="py-1 pr-3 font-medium">{t("analyticsUx.rubricTitle")}</th><th scope="col" className="py-1 pr-3 font-medium">{t("analyticsUx.compareBase")}</th><th scope="col" className="py-1 pr-3 font-medium">{t("analyticsUx.compareTarget")}</th><th scope="col" className="py-1 font-medium">{t("analyticsUx.sumChange")}</th></tr></thead>
                        <tbody>{cmp.rubric_differences.filter((d) => DIMS[d.id]).map((d) => (
                          <tr key={d.id} className="border-t border-border"><th scope="row" className="py-1 pr-3 font-medium">{t(DIMS[d.id])}</th><td className="py-1 pr-3">{num(d.base)}</td><td className="py-1 pr-3">{num(d.target)}</td>
                            <td className="py-1">{d.difference === null ? t("analyticsUx.notMeasured") : `${d.difference > 0 ? "+" : ""}${formatNumber(d.difference)}`}</td></tr>))}</tbody>
                      </table>
                    </div>
                    <p className="text-xs text-muted">{t("analyticsUx.compareLimits")}</p>
                  </div>
                ) : null}
              </CardBody>
            </Card>
          ) : null}
        </>
      )}
    </section>
  );
}
