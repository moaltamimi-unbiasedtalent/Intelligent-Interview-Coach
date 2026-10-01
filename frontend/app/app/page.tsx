import { HomeEntry } from "@/components/coach/HomeEntry";
import { ReturnJourney } from "@/components/home/ReturnJourney";
import { HomeHero } from "@/components/home/HomeHero";
import { OpportunityEntry } from "@/components/home/OpportunityEntry";
import { HomeFeatureBlocks } from "@/components/home/HomeFeatureBlocks";

export const metadata = { title: "Home", robots: { index: false, follow: false } };

// The authenticated candidate home / return journey (Capstone P8 §3 — moved here from `/`,
// which is now the public marketing home). Post-login lands here; the app brand links here.
export default function AppHomePage() {
  return (
    <section className="animate-enter">
      <div className="grid max-w-3xl gap-5 py-8 md:py-12">
        {/* Returning users see a focused continuation card (real data only); first-use
            renders nothing here, preserving the onboarding experience. */}
        <ReturnJourney />
        <HomeHero />
        {/* P10B-W9.4: the job-centric Opportunity entry comes BEFORE the general Prepare composer,
            so the Opportunity mental model is discoverable first. Prepare (HomeEntry) stays below as
            the secondary path — Opportunity creation is never mandatory. */}
        <OpportunityEntry />
        <HomeEntry />
        <HomeFeatureBlocks />
      </div>
    </section>
  );
}
