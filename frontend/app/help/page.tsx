import type { Metadata } from "next";
import Image from "next/image";
import { PageHeader } from "@/components/layout/PageHeader";
import { HelpCenter } from "@/components/help/HelpCenter";

export const metadata: Metadata = { title: "Help" };

export default function HelpPage() {
  return (
    <section data-tour="help">
      <PageHeader
        eyebrow="How Ask4Mo works"
        title="Help"
        description="A searchable guide to every part of Ask4Mo, the ideas behind it, and a replayable guided tour."
      />
      {/* Wave 8 B0: hand-painted watercolor journey (understand -> converse -> practise -> reflect).
          Editorial illustration; its warm paper background is kept inside a clean bordered figure. */}
      <figure className="mx-auto my-8 max-w-[960px] overflow-hidden rounded-lg border border-border">
        <Image
          src="/images/ask4mo/ask4mo-help-journey-watercolor.png"
          alt="An illustrated journey from understanding a role through conversation and practice to reflection."
          width={1536}
          height={1024}
          sizes="(max-width: 960px) 100vw, 960px"
          className="h-auto w-full"
        />
      </figure>
      <HelpCenter />
    </section>
  );
}
