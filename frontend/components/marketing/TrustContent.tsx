"use client";

import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";

// Trust surface (Capstone P8 §9). Factual engineering controls, stated plainly. No
// certification badges. Detailed control statements are engineering copy (English), pending
// localization/legal review (see the release matrix); the page title/subtitle are localized.
const CONTROLS: [string, string][] = [
  ["Account isolation", "Your data is scoped to your account. Platform admins operate a bounded operations console with metadata only — there is no 'view as user' and no private-data search."],
  ["Private by default", "Your CV, answers, reports, Memory and Story Bank are private. Nothing is shared with anyone unless you take an explicit sharing action."],
  ["Explicit workspace sharing", "Sharing into a workspace is view-only and always initiated by you. Removing a share or leaving revokes access."],
  ["Sources you can check", "Grounded answers cite the sources behind them. When evidence is missing, Mo abstains rather than inventing facts."],
  ["Human approvals", "Saving long-term Memory and important handoffs require your explicit approval."],
  ["No hiring decisions", "Ask4Mo does not make or recommend hiring decisions and does not rank candidates for recruiters."],
  ["No voice-trait inference", "Your voice is never used to infer emotion, personality, confidence, accent or hiring suitability. There is no voice score of any kind."],
  ["No audio storage", "Ask4Mo does not record or store your microphone audio. Realtime voice streams to a provider to power the conversation, under that provider's own policy."],
  ["Bounded AI agents", "Mo uses a small, allow-listed set of tools with server-side revalidation. There is no autonomous production self-modification."],
  ["Export & delete", "You can export your data and permanently delete your account and its application-controlled data at any time."],
  ["Provider boundaries", "Long-lived provider keys stay server-side and are never sent to your browser. Costly features have server-side usage limits and an operator pause switch."],
];

export function TrustContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-reading px-4 py-16">
      <h1 className="text-3xl font-bold md:text-4xl">{t("marketing.trustTitle")}</h1>
      <p className="mt-3 text-muted">{t("marketing.trustSubtitle")}</p>
      <dl className="mt-10 space-y-6">
        {CONTROLS.map(([term, desc]) => (
          <div key={term} className="rounded-lg border border-border bg-surface p-5">
            <dt className="font-semibold">{term}</dt>
            <dd className="mt-1 text-sm text-muted">{desc}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-8 text-sm text-muted">
        More detail: <Link href="/privacy" className="underline">Privacy</Link>,{" "}
        <Link href="/ai-transparency" className="underline">AI transparency</Link>,{" "}
        <Link href="/terms" className="underline">Terms</Link>.
      </p>
    </div>
  );
}
