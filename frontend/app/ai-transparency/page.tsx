import type { Metadata } from "next";

import { LegalPage } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: "AI transparency",
  description:
    "How Ask4Mo uses AI: when AI vs deterministic logic runs, specialist agents, RAG/evidence, model limits, human approvals, and what Ask4Mo never infers.",
  alternates: { canonical: "/ai-transparency" },
};

export default function AiTransparencyPage() {
  return (
    <LegalPage title="AI transparency & responsible use" updated="2026-09-26">
      <p>
        We aim to be clear about how AI is used in Ask4Mo, in plain language. This page is an
        engineering draft; the underlying behaviour is described honestly.
      </p>

      <h2>What Mo is</h2>
      <p>
        Mo is an AI coaching assistant that helps you prepare. Mo uses a bounded set of tools and
        follows a governed workflow — it does not act autonomously beyond preparing with you.
      </p>

      <h2>When AI is used vs deterministic logic</h2>
      <ul>
        <li><strong>AI (a model)</strong> is used for conversational coaching, grounded synthesis, question generation and answer/report evaluation.</li>
        <li><strong>Deterministic logic</strong> (no model) is used for things that must be exact and injection-safe — for example selecting and ranking your already-approved evidence.</li>
        <li>The choice of model per operation is governed by a central server-side policy; your browser can never choose a raw model.</li>
      </ul>

      <h2>Specialists, evidence and sources</h2>
      <ul>
        <li>Mo may consult bounded specialists (role/opportunity, evidence, coaching) through allow-listed tools with server-side revalidation.</li>
        <li>Grounded answers cite their sources. When evidence is missing, Mo abstains rather than inventing facts.</li>
      </ul>

      <h2>Human approvals & control</h2>
      <ul>
        <li>Saving long-term Memory and important handoffs require your explicit approval.</li>
        <li>Your feedback helps us improve; it never automatically modifies the running product.</li>
      </ul>

      <h2>Limitations</h2>
      <ul>
        <li>Models can be wrong; Practice scores are guidance, not a verdict.</li>
        <li>Realtime voice is available only where configured; otherwise turn-based voice and typing are used.</li>
      </ul>

      <h2>What Ask4Mo never does</h2>
      <ul>
        <li>No inference of emotion, mood, stress, confidence, accent, personality, intelligence, honesty, or hiring suitability — from your voice or otherwise.</li>
        <li>No hiring decisions and no recruiter-facing candidate ranking.</li>
        <li>No exposure of system prompts, developer prompts, chain-of-thought or secrets.</li>
      </ul>
    </LegalPage>
  );
}
