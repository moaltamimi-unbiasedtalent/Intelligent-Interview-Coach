"use client";

import { useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type {
  GapAnalysisResult,
  InterviewQuestionSet,
  PreparationPlan,
  RoleRequirements,
} from "@/lib/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";

export interface PrepContextPatch {
  targetRole?: string;
  seniority?: string;
  requiredSkills?: string[];
  jobDescription?: string;
  strengths?: string[];
  gaps?: string[];
  priorities?: string[];
}

function errText(e: unknown): string {
  return e instanceof ApiError ? e.userMessage : "That request couldn't be processed.";
}

/** The four existing Career tools, connected to /api/v1/career/*. */
export function PreparationTools({ onContext }: { onContext: (p: PrepContextPatch) => void }) {
  const [jd, setJd] = useState("");
  const [role, setRole] = useState<RoleRequirements | null>(null);
  const [background, setBackground] = useState("");
  const [gaps, setGaps] = useState<GapAnalysisResult | null>(null);
  const [days, setDays] = useState(14);
  const [hours, setHours] = useState(6);
  const [plan, setPlan] = useState<PreparationPlan | null>(null);
  const [roleName, setRoleName] = useState("");
  const [questions, setQuestions] = useState<InterviewQuestionSet | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<Record<string, string>>({});

  async function run(key: string, fn: () => Promise<void>) {
    if (busy) return;
    setBusy(key);
    setErr((e) => ({ ...e, [key]: "" }));
    try {
      await fn();
    } catch (e) {
      setErr((prev) => ({ ...prev, [key]: errText(e) }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-4">
      {/* 1. Job Description Analyzer */}
      <Card>
        <CardBody className="grid gap-3">
          <h3 className="text-base font-semibold">1 · Understand a job description</h3>
          <label htmlFor="tool-jd" className="sr-only">Job description</label>
          <Textarea
            id="tool-jd"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste a job description…"
            className="min-h-[110px]"
          />
          <div>
            <Button
              size="sm"
              disabled={!jd.trim() || busy === "role"}
              onClick={() =>
                run("role", async () => {
                  const res = await api.career.jobAnalysis({ job_description: jd });
                  if (!res.ok || !res.result) throw new ApiError({ kind: "unavailable", status: null, code: res.error || "tool_error", message: res.error || "" });
                  setRole(res.result);
                  setRoleName(res.result.role_title || "");
                  onContext({
                    targetRole: res.result.role_title || undefined,
                    seniority: res.result.seniority || undefined,
                    requiredSkills: res.result.required_skills || [],
                    jobDescription: jd,
                  });
                })
              }
            >
              {busy === "role" ? "Analyzing…" : "Analyze"}
            </Button>
          </div>
          {err.role ? <p className="text-sm text-danger">{err.role}</p> : null}
          {role ? (
            <div className="text-sm">
              <p><span className="text-muted">Role:</span> {role.role_title || "—"} · <span className="text-muted">Seniority:</span> {role.seniority || "—"}</p>
              {role.required_skills?.length ? <p className="mt-1"><span className="text-muted">Required skills:</span> {role.required_skills.join(", ")}</p> : null}
              {role.likely_interview_themes?.length ? <p className="mt-1"><span className="text-muted">Interview themes:</span> {role.likely_interview_themes.join(", ")}</p> : null}
            </div>
          ) : null}
        </CardBody>
      </Card>

      {/* 2. Candidate Gap Analyzer */}
      <Card>
        <CardBody className="grid gap-3">
          <h3 className="text-base font-semibold">2 · Compare your background</h3>
          <p className="text-sm text-muted">Add a little about your experience so the coach can compare the role with your background. Analyze a job description first.</p>
          <label htmlFor="tool-bg" className="sr-only">About you</label>
          <Textarea
            id="tool-bg"
            value={background}
            onChange={(e) => setBackground(e.target.value)}
            placeholder="A few lines about your experience…"
            className="min-h-[90px]"
          />
          <div>
            <Button
              size="sm"
              disabled={!role || !background.trim() || busy === "gaps"}
              onClick={() =>
                run("gaps", async () => {
                  if (!role) return;
                  const res = await api.career.gapAnalysis({ candidate_background: background, role_requirements: role });
                  if (!res.ok || !res.result) throw new ApiError({ kind: "unavailable", status: null, code: res.error || "tool_error", message: res.error || "" });
                  setGaps(res.result);
                  onContext({
                    strengths: res.result.strengths || [],
                    gaps: res.result.missing || [],
                    priorities: (res.result.priority_gaps || []).map((g) => g.requirement),
                  });
                })
              }
            >
              {busy === "gaps" ? "Comparing…" : "Compare"}
            </Button>
          </div>
          {err.gaps ? <p className="text-sm text-danger">{err.gaps}</p> : null}
          {gaps ? (
            <div className="text-sm">
              <p><span className="text-muted">Match:</span> {gaps.stats.match_percentage}% ({gaps.stats.matched}/{gaps.stats.total_requirements})</p>
              {gaps.priority_gaps?.length ? (
                <ul className="mt-2 space-y-1">
                  {gaps.priority_gaps.map((g, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span>{g.requirement}</span>
                      {g.severity ? <Badge tone={g.severity.toLowerCase() === "high" ? "high" : g.severity.toLowerCase() === "medium" ? "medium" : "low"}>{g.severity}</Badge> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </CardBody>
      </Card>

      {/* 3. Preparation Plan */}
      <Card>
        <CardBody className="grid gap-3">
          <h3 className="text-base font-semibold">3 · Build a preparation plan</h3>
          <div className="flex flex-wrap gap-3">
            <label className="text-sm">Days until interview
              <Input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))} className="mt-1 w-28" />
            </label>
            <label className="text-sm">Hours per week
              <Input type="number" min={1} max={80} step={0.5} value={hours} onChange={(e) => setHours(Number(e.target.value))} className="mt-1 w-28" />
            </label>
          </div>
          <div>
            <Button
              size="sm"
              disabled={!gaps?.priority_gaps?.length || busy === "plan"}
              onClick={() =>
                run("plan", async () => {
                  const res = await api.career.preparationPlan({ priority_gaps: gaps!.priority_gaps, days_until_interview: days, hours_per_week: hours });
                  if (!res.ok || !res.result) throw new ApiError({ kind: "unavailable", status: null, code: res.error || "tool_error", message: res.error || "" });
                  setPlan(res.result);
                })
              }
            >
              {busy === "plan" ? "Building…" : "Build plan"}
            </Button>
          </div>
          {err.plan ? <p className="text-sm text-danger">{err.plan}</p> : null}
          {plan ? (
            <div className="text-sm">
              <p><span className="text-muted">Total available:</span> {plan.total_available_hours}h</p>
              <ul className="mt-2 space-y-1">
                {plan.allocations.map((a, i) => (
                  <li key={i}>{a.requirement} — {a.allocated_hours}h ({a.share_percentage}%)</li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardBody>
      </Card>

      {/* 4. Interview Question Generator */}
      <Card>
        <CardBody className="grid gap-3">
          <h3 className="text-base font-semibold">4 · Generate practice questions</h3>
          <label htmlFor="tool-role" className="sr-only">Role</label>
          <Input id="tool-role" value={roleName} onChange={(e) => setRoleName(e.target.value)} placeholder="Role, e.g. Senior Product Manager" />
          <div>
            <Button
              size="sm"
              disabled={!roleName.trim() || busy === "q"}
              onClick={() =>
                run("q", async () => {
                  const requirements = role ? [...(role.required_skills || []), ...(role.technologies || [])] : [];
                  const res = await api.career.questions({ role: roleName, requirements, focus: [] });
                  if (!res.ok || !res.result) throw new ApiError({ kind: "unavailable", status: null, code: res.error || "tool_error", message: res.error || "" });
                  setQuestions(res.result);
                  onContext({ targetRole: roleName });
                })
              }
            >
              {busy === "q" ? "Generating…" : "Generate questions"}
            </Button>
          </div>
          {err.q ? <p className="text-sm text-danger">{err.q}</p> : null}
          {questions ? (
            <div className="text-sm">
              {questions.categories.map((c, i) => (
                <div key={i} className="mt-2">
                  <p className="font-medium">{c.name}</p>
                  <ul className="mt-1 list-disc pl-5 text-muted">
                    {c.questions.map((q, j) => <li key={j}>{q}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}
