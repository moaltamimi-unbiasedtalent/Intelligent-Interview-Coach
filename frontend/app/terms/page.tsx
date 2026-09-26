import type { Metadata } from "next";

import { LegalPage } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: "Terms of use",
  description:
    "Terms for using Ask4Mo. AI preparation guidance is not professional, legal or employment advice. Engineering draft — pending legal review.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of use" updated="2026-09-26">
      <p>
        These terms are an <strong>engineering draft and require legal review</strong> before
        public launch. They set expectations for using Ask4Mo during staging/product review.
      </p>

      <h2>What Ask4Mo is</h2>
      <p>
        Ask4Mo provides <strong>AI-assisted interview preparation guidance</strong>. It is a
        preparation aid, <strong>not professional, legal, financial or employment advice</strong>,
        and not a substitute for your own judgement.
      </p>

      <h2>AI limitations</h2>
      <ul>
        <li>AI can be wrong or incomplete. Verify anything important against the cited sources.</li>
        <li>Sources may be partial; some datasets ship with an explicit &quot;engineering draft&quot; or &quot;unvalidated&quot; status.</li>
        <li>Practice scores are <strong>preparation guidance</strong>, not an objective measure of ability or a prediction of interview outcomes.</li>
        <li>Ask4Mo does <strong>not</strong> make hiring decisions, rank candidates for recruiters, or evaluate you by your voice.</li>
      </ul>

      <h2>Your responsibilities</h2>
      <ul>
        <li>Provide accurate information and keep your credentials secure.</li>
        <li>Only upload content you have the right to use.</li>
        <li>Use the service lawfully and do not attempt to abuse or overload it.</li>
      </ul>

      <h2>Accounts, plans and availability</h2>
      <ul>
        <li>Basic is free. Premium is presented as a preview; <strong>no online payment is processed by this product</strong>.</li>
        <li>Some features depend on external providers and may be unavailable, rate-limited or paused by the operator.</li>
        <li>The service is provided &quot;as is&quot; during this pre-launch phase, without warranties; liability is limited to the maximum extent permitted by applicable law (subject to legal review).</li>
      </ul>

      <h2>Changes</h2>
      <p>These terms will be revised and legally reviewed before any public launch.</p>
    </LegalPage>
  );
}
