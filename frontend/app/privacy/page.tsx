import type { Metadata } from "next";

import { LegalPage } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "How Ask4Mo handles your data: what is collected, how it is used, retention, export and deletion. Engineering draft — pending legal review.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy" updated="2026-09-26">
      <p>
        This page describes how Ask4Mo handles your data, based on the product&apos;s actual
        technical data inventory. It is an <strong>engineering draft and requires legal
        review</strong>; it is not a certification of compliance with any regulation.
      </p>

      <h2>What we store</h2>
      <ul>
        <li><strong>Account data</strong>: email, display name, verification status, sign-in method, plan tier and platform role.</li>
        <li><strong>Preparation data</strong>: your goals, conversations with Mo and generated preparation context.</li>
        <li><strong>Private documents</strong>: files you upload (e.g. CV) stored privately under a random key — never a public URL. OCR-extracted text and detected claims.</li>
        <li><strong>Interview Practice</strong>: your answers, evaluations and reports.</li>
        <li><strong>Memory</strong>: long-term preparation facts you have explicitly approved.</li>
        <li><strong>Story Bank</strong>: reusable evidence-backed stories you create.</li>
        <li><strong>Workspaces & sharing</strong>: workspaces you own or join, and the specific items you explicitly share.</li>
        <li><strong>Feedback</strong>: ratings/comments you submit on responses.</li>
        <li><strong>Operational metadata</strong>: request identifiers, timestamps, coarse event categories and audit records of privileged/security-relevant actions.</li>
      </ul>

      <h2>Voice, speech and realtime</h2>
      <ul>
        <li>Turn-based voice uses your browser/OS speech engines. <strong>Ask4Mo does not record or store your microphone audio.</strong></li>
        <li>Realtime voice (where enabled) streams audio to a realtime provider to power the live conversation; that processing follows the provider&apos;s own policy. Ask4Mo still stores no audio.</li>
        <li>Ask4Mo never uses your voice to infer emotion, personality, confidence, accent or hiring suitability. There is no voice score.</li>
      </ul>

      <h2>External processing</h2>
      <ul>
        <li>AI features send necessary text (not secrets) to a model provider to generate responses.</li>
        <li>Current-market research (optional) may query external job-market sources.</li>
        <li>Email delivery uses a transactional email provider for verification and recovery.</li>
        <li>Long-lived provider keys stay server-side and are never sent to your browser.</li>
      </ul>

      <h2>Retention, export and deletion</h2>
      <ul>
        <li>You can <strong>export</strong> your data and <strong>permanently delete</strong> your account and its application-controlled data (documents, private files, Practice history, Memory, Story Bank, sessions and agent checkpoints).</li>
        <li>Security/audit records are retained and anonymized (the link to your account is removed) rather than deleted, for security review.</li>
        <li>Historical infrastructure <strong>backups</strong> follow the hosting provider&apos;s retention schedule and are not erased instantly on deletion; they age out per that schedule.</li>
        <li>Privacy, security and your data rights are always available, on every plan.</li>
      </ul>

      <h2>Contact</h2>
      <p>
        For privacy requests, contact the support address configured for your deployment. This
        draft will be replaced by legally-reviewed copy before public launch.
      </p>
    </LegalPage>
  );
}
