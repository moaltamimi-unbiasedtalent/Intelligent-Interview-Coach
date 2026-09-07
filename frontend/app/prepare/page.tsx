import type { Metadata } from "next";
import { CoachActivity, CoachMessage } from "@/components/coach/CoachMessage";
import { CoachComposer } from "@/components/coach/CoachComposer";
import { HumanApprovalCard } from "@/components/preparation/HumanApprovalCard";
import { PrepareResponsive } from "@/components/preparation/PrepareResponsive";
import { PreparationPriority } from "@/components/preparation/PreparationPriority";
import { RoleContext } from "@/components/preparation/RoleContext";
import { SourceList } from "@/components/preparation/SourceList";
import { StageProgress } from "@/components/preparation/StageProgress";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";

export const metadata: Metadata = { title: "Prepare" };

// DEMO scaffold content — replaced with live FastAPI responses in Phase 3C.
export default function PreparePage() {
  const coach = (
    <div className="animate-enter">
      <div className="grid gap-3.5">
        <CoachMessage from="you">
          What should I focus on with two weeks to prepare?
        </CoachMessage>
        <CoachMessage from="coach">
          <p>
            Three areas will move the needle most. You&rsquo;re strong on stakeholder
            leadership and discovery, so let&rsquo;s spend the time where the gaps are:
          </p>
          <p className="mt-2.5">
            1 · <strong>Executive communication</strong> — framing trade-offs for a
            leadership audience.
            <br />2 · <strong>Commercial ownership</strong> — tying roadmap choices to
            revenue and margin.
            <br />3 · <strong>Experimentation rigor</strong> — a lighter gap, worth one
            example.
          </p>
          <div className="mt-3">
            <SourceList summary="O*NET · ESCO · 4 more" detail="O*NET 11-3051 · ESCO Product manager · UK labour-market profile · 2 role postings (demo)" />
          </div>
        </CoachMessage>
        <CoachActivity label="Comparing your preparation areas…" />
      </div>
      <CoachComposer />
      <div className="mt-5">
        <HumanApprovalCard
          title="I think this role is closest to Senior Product Manager."
          description="Confirm so the preparation stays on target."
          confirmLabel="Confirm"
          dismissLabel="Choose another"
        />
      </div>
    </div>
  );

  const context = (
    <>
      <Card>
        <CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Your strengths</h3>
          <div className="mt-2 space-y-2 text-sm">
            <p className="font-medium">Stakeholder leadership <span className="block text-muted">Seen across your last two roles</span></p>
            <p className="font-medium">Product discovery <span className="block text-muted">Strong signal in your CV</span></p>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Priorities to prepare</h3>
          <div className="mt-1">
            <PreparationPriority priority={{ title: "Executive communication", severity: "high", note: "Most-cited requirement for this level" }} />
            <PreparationPriority priority={{ title: "Commercial ownership", severity: "medium", note: "Appears in the job description" }} />
            <PreparationPriority priority={{ title: "Experimentation rigor", severity: "low", note: "One example is enough" }} />
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="grid gap-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Ready when you are</h3>
          <p className="text-sm text-muted">Practise the areas we&rsquo;ve identified.</p>
          <Button>Start interview practice →</Button>
        </CardBody>
      </Card>
    </>
  );

  return (
    <section>
      <div className="mb-4">
        <StageProgress current="Prepare" />
      </div>
      <div className="mb-5">
        <RoleContext
          data={{ role: "Senior Product Manager", seniority: "Senior", geography: "United Kingdom", company: "Northwind · demo", readiness: 72 }}
        />
      </div>
      <PrepareResponsive coach={coach} context={context} />
      <p className="mt-8 text-xs text-muted">DEMO content — live preparation is wired in Phase 3C.</p>
    </section>
  );
}
