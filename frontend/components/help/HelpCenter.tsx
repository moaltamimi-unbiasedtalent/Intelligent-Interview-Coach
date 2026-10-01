"use client";

import { useMemo, useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { TutorialLauncher } from "@/components/tutorial/TutorialLauncher";
import { useT } from "@/components/i18n/I18nProvider";

interface Article {
  q: string;
  a: string;
}
interface Section {
  id: string;
  title: string;
  articles: Article[];
}

/**
 * The permanent Help Center STRUCTURE. Section ids/order and article counts live here; every
 * candidate-facing string (section titles + article questions/answers) lives in the i18n `help`
 * namespace (P10B-W9.6A, lib/i18n/messages/w96/help), resolved via t() at render so Help localises
 * with the interface language. Deterministic docs: no LLM, no embeddings.
 */
const HELP_SECTIONS: { id: string; titleKey: string; articles: { q: string; a: string }[] }[] = [
  {
    id: "getting-started",
    titleKey: "help.gsTitle",
    articles: [
      { q: "help.gs1q", a: "help.gs1a" },
      { q: "help.gs2q", a: "help.gs2a" },
      { q: "help.gs3q", a: "help.gs3a" },
      { q: "help.gs4q", a: "help.gs4a" },
    ],
  },
  {
    id: "prepare",
    titleKey: "help.prepTitle",
    articles: [
      { q: "help.prep1q", a: "help.prep1a" },
      { q: "help.prep2q", a: "help.prep2a" },
      { q: "help.prep3q", a: "help.prep3a" },
      { q: "help.prep4q", a: "help.prep4a" },
      { q: "help.prep5q", a: "help.prep5a" },
      { q: "help.prep6q", a: "help.prep6a" },
    ],
  },
  {
    id: "practice",
    titleKey: "help.pracTitle",
    articles: [
      { q: "help.prac1q", a: "help.prac1a" },
      { q: "help.prac2q", a: "help.prac2a" },
      { q: "help.prac3q", a: "help.prac3a" },
      { q: "help.prac4q", a: "help.prac4a" },
    ],
  },
  {
    id: "progress",
    titleKey: "help.progTitle",
    articles: [
      { q: "help.prog1q", a: "help.prog1a" },
      { q: "help.prog2q", a: "help.prog2a" },
    ],
  },
  {
    id: "history",
    titleKey: "help.histTitle",
    articles: [
      { q: "help.hist1q", a: "help.hist1a" },
      { q: "help.hist2q", a: "help.hist2a" },
      { q: "help.hist3q", a: "help.hist3a" },
      { q: "help.hist4q", a: "help.hist4a" },
    ],
  },
  {
    id: "sources",
    titleKey: "help.srcTitle",
    articles: [
      { q: "help.src1q", a: "help.src1a" },
      { q: "help.src2q", a: "help.src2a" },
      { q: "help.src3q", a: "help.src3a" },
      { q: "help.src4q", a: "help.src4a" },
      { q: "help.src5q", a: "help.src5a" },
    ],
  },
  {
    id: "dictation",
    titleKey: "help.dictTitle",
    articles: [
      { q: "help.dict1q", a: "help.dict1a" },
      { q: "help.dict2q", a: "help.dict2a" },
      { q: "help.dict3q", a: "help.dict3a" },
      { q: "help.dict4q", a: "help.dict4a" },
      { q: "help.dict5q", a: "help.dict5a" },
      { q: "help.dict6q", a: "help.dict6a" },
      { q: "help.dict7q", a: "help.dict7a" },
      { q: "help.dict8q", a: "help.dict8a" },
    ],
  },
  {
    id: "documents",
    titleKey: "help.docTitle",
    articles: [
      { q: "help.doc1q", a: "help.doc1a" },
      { q: "help.doc2q", a: "help.doc2a" },
      { q: "help.doc3q", a: "help.doc3a" },
      { q: "help.doc4q", a: "help.doc4a" },
      { q: "help.doc5q", a: "help.doc5a" },
      { q: "help.doc6q", a: "help.doc6a" },
      { q: "help.doc7q", a: "help.doc7a" },
      { q: "help.doc8q", a: "help.doc8a" },
      { q: "help.doc9q", a: "help.doc9a" },
      { q: "help.doc10q", a: "help.doc10a" },
      { q: "help.doc11q", a: "help.doc11a" },
      { q: "help.doc12q", a: "help.doc12a" },
      { q: "help.doc13q", a: "help.doc13a" },
    ],
  },
  {
    id: "memory",
    titleKey: "help.memTitle",
    articles: [
      { q: "help.mem1q", a: "help.mem1a" },
      { q: "help.mem2q", a: "help.mem2a" },
      { q: "help.mem3q", a: "help.mem3a" },
    ],
  },
  {
    id: "privacy",
    titleKey: "help.privTitle",
    articles: [
      { q: "help.priv1q", a: "help.priv1a" },
      { q: "help.priv2q", a: "help.priv2a" },
      { q: "help.priv3q", a: "help.priv3a" },
      { q: "help.priv4q", a: "help.priv4a" },
    ],
  },
  {
    id: "troubleshooting",
    titleKey: "help.tsTitle",
    articles: [
      { q: "help.ts1q", a: "help.ts1a" },
      { q: "help.ts2q", a: "help.ts2a" },
      { q: "help.ts3q", a: "help.ts3a" },
      { q: "help.ts4q", a: "help.ts4a" },
      { q: "help.ts5q", a: "help.ts5a" },
      { q: "help.ts6q", a: "help.ts6a" },
      { q: "help.ts7q", a: "help.ts7a" },
      { q: "help.ts8q", a: "help.ts8a" },
    ],
  },
  {
    id: "reviewer",
    titleKey: "help.revTitle",
    articles: [
      { q: "help.rev1q", a: "help.rev1a" },
      { q: "help.rev2q", a: "help.rev2a" },
      { q: "help.rev3q", a: "help.rev3a" },
      { q: "help.rev4q", a: "help.rev4a" },
      { q: "help.rev5q", a: "help.rev5a" },
    ],
  },
];

export function HelpCenter() {
  const [query, setQuery] = useState("");
  const t = useT();

  // All Help content is localised via the i18n `help` namespace (P10B-W9.6A); the P7/P7.5 Voice
  // section reuses the `voice` namespace. Section structure (ids/order/counts) stays in code.
  const sections = useMemo<Section[]>(() => {
    const built: Section[] = HELP_SECTIONS.map((s) => ({
      id: s.id,
      title: t(s.titleKey),
      articles: s.articles.map((a) => ({ q: t(a.q), a: t(a.a) })),
    }));
    const voice: Section = {
      id: "voice",
      title: t("voice.helpTitle"),
      articles: [
        { q: t("voice.hListenQ"), a: t("voice.hListenA") },
        { q: t("voice.hSpeakQ"), a: t("voice.hSpeakA") },
        { q: t("voice.hLangQ"), a: t("voice.hLangA") },
        { q: t("voice.hPrivacyQ"), a: t("voice.hPrivacyA") },
        { q: t("voice.hUnsupportedQ"), a: t("voice.hUnsupportedA") },
        // Realtime voice (Capstone P7.5, C1).
        { q: t("voice.hRealtimeQ"), a: t("voice.hRealtimeA") },
        { q: t("voice.hRealtimeInterruptQ"), a: t("voice.hRealtimeInterruptA") },
        { q: t("voice.hRealtimeFallbackQ"), a: t("voice.hRealtimeFallbackA") },
        { q: t("voice.hRealtimeAudioQ"), a: t("voice.hRealtimeAudioA") },
      ],
    };
    return [...built, voice];
  }, [t]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sections;
    return sections.map((s) => ({
      ...s,
      articles: s.articles.filter(
        (a) =>
          s.title.toLowerCase().includes(q) ||
          a.q.toLowerCase().includes(q) ||
          a.a.toLowerCase().includes(q),
      ),
    })).filter((s) => s.articles.length > 0);
  }, [query, sections]);

  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold">{t("help.tourTitle")}</h2>
            <p className="text-sm text-muted">{t("help.tourBody")}</p>
          </div>
          <TutorialLauncher />
        </CardBody>
      </Card>

      <div>
        <label htmlFor="help-search" className="sr-only">{t("help.searchLabel")}</label>
        <Input
          id="help-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("help.searchExamples")}
        />
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-muted">{t("help.noMatch", { query })}</p>
      ) : (
        filtered.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-24">
            <h2 className="mb-2 text-sm font-semibold text-foreground">{s.title}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {s.articles.map((a) => (
                <Card key={a.q}>
                  <CardBody>
                    <h3 className="text-sm font-semibold">{a.q}</h3>
                    <p className="mt-1 text-sm text-muted">{a.a}</p>
                  </CardBody>
                </Card>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
