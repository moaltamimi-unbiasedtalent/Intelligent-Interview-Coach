import type { Metadata } from "next";

import { ButtonLink } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "About",
  description:
    "About Ask4Mo — an intelligent interview coach built to be trustworthy: grounded, private by default, and honest about its limitations.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-reading px-4 py-16">
      <h1 className="text-3xl font-bold md:text-4xl">About Ask4Mo</h1>
      <p className="mt-4 text-muted">
        Ask4Mo — the Intelligent Interview Coach — helps candidates prepare for interviews that
        matter. Its guiding idea is simple: <strong>Ask More. Be More.</strong> Better questions,
        grounded answers and honest practice lead to better outcomes.
      </p>
      <p className="mt-4 text-muted">
        Ask4Mo is built to be trustworthy first. Preparation is grounded in sources you can check,
        your data is private by default, AI decisions that matter require your approval, and the
        product is honest about what it can and cannot do. It does not make hiring decisions, rank
        candidates for recruiters, or judge you by your voice.
      </p>
      <p className="mt-4 text-muted">
        This is a Capstone product. Some capabilities (for example live realtime voice and certain
        knowledge datasets) ship with an honest, clearly-stated validation status rather than
        overclaiming. See our{" "}
        <a href="/trust" className="underline">Trust</a> and{" "}
        <a href="/ai-transparency" className="underline">AI transparency</a> pages.
      </p>
      <p className="mt-6 text-sm text-muted">
        Questions or privacy requests? Contact support at the address configured for your
        deployment (see the Help centre once signed in).
      </p>
      <div className="mt-8">
        <ButtonLink href="/register">Get started free</ButtonLink>
      </div>
    </div>
  );
}
