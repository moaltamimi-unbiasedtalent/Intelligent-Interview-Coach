# Provisional Component Inventory

For later translation to Next.js + TypeScript + Tailwind. **Not implemented in
Phase 3A** — this scopes the future build and clarifies which surface each
component belongs to.

## Candidate components (coaching experience)

| Component | Role |
|-----------|------|
| `AppShell` | Top nav + content region + responsive nav collapse |
| `TopNavigation` | Primary nav (Home · Prepare · Practice · Progress · History) |
| `HomeHero` | Value proposition + the single primary action |
| `PrepareEntry` | Role description / JD paste / optional CV (progressive) |
| `CoachComposer` | Plain-language input to the coach |
| `CoachMessage` | A coach turn (answer + optional inline sources/actions) |
| `AgentActivity` | Safe observable-action status ("Reviewing the requirements") |
| `PreparationSummary` | Role context + overall readiness at a glance |
| `RoleContext` | Target role · seniority · geography · company |
| `StrengthCard` | A candidate strength (evidence-linked) |
| `GapCard` | A gap/priority with severity + "why" affordance |
| `PreparationStep` | A next-action item in the plan |
| `SourceList` | Collapsed "Sources: … · N more" → expandable provenance |
| `InterviewQuestion` | Distraction-free question presentation + progress |
| `AnswerComposer` | Type input |
| `RecordingControl` | Record answer (Record mode) |
| `AnswerFeedback` | Per-answer feedback (scores + actionable notes) |
| `PerformanceSummary` | Review: strengths · improvements · next practice |
| `HumanApproval` | Role-confirmation HITL card |
| `MemoryConsent` | Memory-save HITL card |
| `HandoffCard` | "Ready to practise?" transition |
| `EmptyState` / `ErrorState` / `InsufficientInfo` | Cross-cutting states |

## Shared components (design-system primitives)

`Button` · `Card` · `Tag`/`Badge` · `ProgressIndicator` · `Tabs` · `Sheet`/`Drawer`
(mobile context) · `Disclosure`/`Accordion` · `Avatar` · `Tooltip` · `Toast` ·
`SegmentedControl` (Type/Record) · `ThemeToggle` · `SkipLink`.

## Diagnostic-only components (Review & Diagnostics)

| Component | Role |
|-----------|------|
| `AgentInspectorRun` | One run: goal, status, timeline |
| `RunStepRow` | A step: tool available/selected, retrieval, sources, latency |
| `MemoryTraceRow` | Memory read/write (safe metadata) |
| `ApprovalTraceRow` | Where a human approval gated an action |
| `UsageMeter` | Tokens / estimated cost / latency |
| `SourceProvenanceTable` | Fuller provenance than the candidate `SourceList` |

Diagnostic components may look slightly more technical but stay inside the same
design system (tokens, type, spacing). They never render chain-of-thought, system
prompts, raw provider payloads, or secrets.
