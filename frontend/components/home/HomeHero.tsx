"use client";

import { useT } from "@/components/i18n/I18nProvider";

/** Localized hero text for the home entry (Capstone P3.5). */
export function HomeHero() {
  const t = useT();
  return (
    <>
      <div>
        <p className="text-2xl font-bold tracking-tight text-accent">{t("common.appName")}</p>
        <p className="text-sm font-semibold text-muted">{t("common.productName")}</p>
      </div>
      <h1 className="text-4xl font-semibold tracking-tight md:text-5xl lg:text-6xl">
        {t("home.headline")}
      </h1>
      <p className="text-lg font-semibold text-foreground">{t("common.tagline")}</p>
      <p className="max-w-reading text-lg text-muted">{t("home.subcopy")}</p>
    </>
  );
}
