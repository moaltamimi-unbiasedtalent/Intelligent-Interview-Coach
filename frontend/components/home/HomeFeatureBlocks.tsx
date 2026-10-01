"use client";

import { useT } from "@/components/i18n/I18nProvider";

// The four authenticated-Home feature blocks. P10B-W9.7A: previously a hardcoded English string-tuple
// array in the server page `app/app/page.tsx` (invisible to the W9.6 scanner), so it stayed English under
// every other interface language. Now rendered via the catalogue (`home.feat*`), interface-language owned.
const BLOCKS = ["feat1", "feat2", "feat3", "feat4"] as const;

export function HomeFeatureBlocks() {
  const t = useT();
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2" data-testid="home-feature-blocks">
      {BLOCKS.map((k) => (
        <div key={k}>
          <p className="text-sm font-semibold text-foreground">{t(`home.${k}Title`)}</p>
          <p className="text-sm text-muted">{t(`home.${k}Body`)}</p>
        </div>
      ))}
    </div>
  );
}
