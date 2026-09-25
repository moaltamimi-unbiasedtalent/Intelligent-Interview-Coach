import { HomeEntry } from "@/components/coach/HomeEntry";
import { ReturnJourney } from "@/components/home/ReturnJourney";
import { HomeHero } from "@/components/home/HomeHero";

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
        <HomeEntry />
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {[
            ["Prepare with evidence", "Grounded career information and citations when needed."],
            ["Practise with purpose", "Tailored questions based on the role and your preparation context."],
            ["Stay in control", "Memory and important handoffs require clear approval."],
            ["Improve over time", "Structured feedback, progress and reusable preparation context."],
          ].map(([title, body]) => (
            <div key={title}>
              <p className="text-sm font-semibold text-foreground">{title}</p>
              <p className="text-sm text-muted">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
