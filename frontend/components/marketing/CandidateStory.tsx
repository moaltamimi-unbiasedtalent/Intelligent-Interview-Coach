"use client";

// Static candidate story (v4). Still images only (no video). Fictional candidate, AI-generated imagery, never a
// testimonial and never an implied job offer. The "patterns" and "reflection" scenes are PRODUCT DIRECTION and are
// labelled as not available; only the first three scenes describe the current product journey.

import Image from "next/image";

import { useT } from "@/components/i18n/I18nProvider";

type Scene = { id: string; src: string; captionKey: string; altKey: string; direction?: boolean };

const SRC = "/images/ask4mo/ask4mo-v4-candidate-story-";
const CURRENT: Scene[] = [
  { id: "rejection", src: `${SRC}rejection.png`, captionKey: "gettingStarted.sceneRejectionCaption", altKey: "gettingStarted.sceneRejectionAlt" },
  { id: "practice", src: `${SRC}practice.png`, captionKey: "gettingStarted.scenePracticeCaption", altKey: "gettingStarted.scenePracticeAlt" },
  { id: "ready", src: `${SRC}ready.png`, captionKey: "gettingStarted.sceneReadyCaption", altKey: "gettingStarted.sceneReadyAlt" },
];
const DIRECTION: Scene[] = [
  { id: "patterns", src: `${SRC}patterns.png`, captionKey: "gettingStarted.scenePatternsCaption", altKey: "gettingStarted.scenePatternsAlt", direction: true },
  { id: "reflection", src: `${SRC}reflection.png`, captionKey: "gettingStarted.sceneReflectionCaption", altKey: "gettingStarted.sceneReflectionAlt", direction: true },
];

export function CandidateStory({ compact = false }: { compact?: boolean }) {
  const t = useT();
  const scenes = compact ? CURRENT.slice(0, 3) : [...CURRENT, ...DIRECTION];
  return (
    <div data-testid="candidate-story">
      <ol className={compact ? "grid gap-4 md:grid-cols-3" : "grid gap-4 sm:grid-cols-2 lg:grid-cols-3"}>
        {scenes.map((s) => (
          <li key={s.id} data-scene={s.id} className="overflow-hidden rounded-lg border border-border bg-surface">
            <figure>
              <div className="relative aspect-video w-full">
                <Image src={s.src} alt={t(s.altKey)} fill sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 380px" className="object-cover" />
              </div>
              <figcaption className="p-4 text-sm text-muted">
                {s.direction ? (
                  <span className="mb-2 inline-block rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs font-semibold text-foreground" data-testid="direction-label">
                    {t("gettingStarted.directionLabel")}
                  </span>
                ) : null}
                <span className="block">{t(s.captionKey)}</span>
                {s.direction ? <span className="mt-1 block text-xs">{t("gettingStarted.directionNote")}</span> : null}
              </figcaption>
            </figure>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-muted" data-testid="story-disclosure">
        {t("gettingStarted.storyDisclosure")} {t("gettingStarted.storyNotTestimonial")}
      </p>
    </div>
  );
}
