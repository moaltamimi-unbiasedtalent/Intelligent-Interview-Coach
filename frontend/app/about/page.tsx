import type { Metadata } from "next";
import Image from "next/image";

import { ButtonLink } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "About",
  description:
    "About Ask4Mo - an intelligent interview coach built to be trustworthy: grounded, private by default, and honest about its limitations.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-reading px-4 py-16">
      <h1 className="text-3xl font-bold md:text-4xl">About Ask4Mo</h1>
      <p className="mt-4 text-muted">
        Ask4Mo - the Intelligent Interview Coach - helps candidates prepare for interviews that
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
      {/* Wave 8 B0: candid coaching conversation. Illustrative AI-generated brand photography - the
          depicted people are not Ask4Mo employees, customers or testimonial subjects. */}
      <figure className="mt-8 overflow-hidden rounded-lg border border-border">
        <Image
          src="/images/ask4mo/ask4mo-about-human-conversation.png"
          alt="Two people having a thoughtful coaching conversation in a quiet library."
          width={1448}
          height={1086}
          sizes="(max-width: 720px) 100vw, 720px"
          className="h-auto w-full"
        />
      </figure>
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
