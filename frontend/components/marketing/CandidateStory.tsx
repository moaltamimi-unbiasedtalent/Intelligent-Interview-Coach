"use client";

// Static candidate story (v4.3). Still images only (no video). The three current-journey scenes use varied,
// documentary-style fictional photography instead of repeating one staged room. Future concepts are deliberately
// rendered as product diagrams, not as fake screenshots or invented customer proof.

import Image from "next/image";

import { useT } from "@/components/i18n/I18nProvider";

type Scene = { id: string; src: string; captionKey: string; altKey: string };

const SRC = "/images/ask4mo/ask4mo-v4-candidate-story-";
const CURRENT: Scene[] = [
  { id: "rejection", src: `${SRC}rejection-v2.png`, captionKey: "gettingStarted.sceneRejectionCaption", altKey: "gettingStarted.sceneRejectionAlt" },
  { id: "practice", src: `${SRC}practice-v5.png`, captionKey: "gettingStarted.scenePracticeCaption", altKey: "gettingStarted.scenePracticeAlt" },
  { id: "ready", src: `${SRC}ready-v2.png`, captionKey: "gettingStarted.sceneReadyCaption", altKey: "gettingStarted.sceneReadyAlt" },
];
const DIRECTION = [
  { id: "patterns", src: "/images/ask4mo/ask4mo-v4-candidate-story-patterns-concept.png", captionKey: "gettingStarted.scenePatternsCaption", altKey: "gettingStarted.scenePatternsAlt" },
  { id: "reflection", src: "/images/ask4mo/ask4mo-v4-candidate-story-reflection-concept.png", captionKey: "gettingStarted.sceneReflectionCaption", altKey: "gettingStarted.sceneReflectionAlt" },
] as const;

export function CandidateStory({ compact = false }: { compact?: boolean }) {
  const t = useT();
  return (
    <div data-testid="candidate-story">
      <ol className="grid gap-4 md:grid-cols-3">
        {CURRENT.map((scene, index) => (
          <li key={scene.id} data-scene={scene.id} className="group overflow-hidden rounded-[1.25rem] border border-border bg-surface shadow-sm">
            <figure>
              <div className="relative aspect-[16/10] w-full overflow-hidden">
                <Image
                  src={scene.src}
                  alt={t(scene.altKey)}
                  fill
                  sizes="(max-width: 768px) 100vw, 380px"
                  className="object-cover transition-transform duration-500 group-hover:scale-[1.02] motion-reduce:transition-none"
                />
                <span className="absolute left-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-black/65 text-sm font-bold text-white backdrop-blur-sm" aria-hidden="true">{index + 1}</span>
              </div>
              <figcaption className="p-4 text-sm text-muted">{t(scene.captionKey)}</figcaption>
            </figure>
          </li>
        ))}
      </ol>

      {!compact ? (
        <ol className="mt-6 grid gap-4 md:grid-cols-2">
          {DIRECTION.map((scene) => (
            <li key={scene.id} data-scene={scene.id} className="grid overflow-hidden rounded-[1.25rem] border border-dashed border-accent/40 bg-surface md:grid-cols-[11rem_1fr]">
              <div className="relative min-h-36 overflow-hidden">
                <Image src={scene.src} alt={t(scene.altKey)} fill sizes="176px" className="object-cover" />
              </div>
              <div className="p-5">
                <span className="inline-block rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs font-semibold text-foreground" data-testid="direction-label">
                  {t("gettingStarted.directionLabel")}
                </span>
                <p className="mt-3 text-sm text-muted">{t(scene.captionKey)}</p>
                <p className="mt-1 text-xs text-muted">{t("gettingStarted.directionNote")}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      <p className="mt-3 text-xs text-muted" data-testid="story-disclosure">
        {t("gettingStarted.storyDisclosure")} {t("gettingStarted.storyNotTestimonial")}
      </p>
    </div>
  );
}
