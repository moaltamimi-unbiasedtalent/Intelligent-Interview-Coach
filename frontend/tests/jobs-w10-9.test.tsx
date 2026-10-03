import { readFileSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W10.9 Admin jobs UI. Raw payloads never reach the browser; async content awaited with findBy*.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/jobs" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const list = vi.fn();
const one = vi.fn();
const diag = vi.fn();
const types = vi.fn();
const enqueue = vi.fn();
const retry = vi.fn();
const cancel = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { admin: { jobs: (...a: unknown[]) => list(...a), job: (...a: unknown[]) => one(...a), jobDiagnostics: (...a: unknown[]) => diag(...a),
    jobTypes: (...a: unknown[]) => types(...a), enqueueJob: (...a: unknown[]) => enqueue(...a), retryJob: (...a: unknown[]) => retry(...a),
    cancelJob: (...a: unknown[]) => cancel(...a) } },
}));

import { JobDetailView } from "@/components/admin/JobDetailView";
import { JobsView } from "@/components/admin/JobsView";

const JOB = (over: Record<string, unknown> = {}) => ({
  public_id: "a".repeat(32), job_type: "diagnostic_noop", type_label: "Operational diagnostic (no-op)", state: "queued", priority: "normal",
  attempts: 0, max_attempts: 2, manual_retries: 0, available_at: "2026-10-03T10:00:00+00:00", created_at: "2026-10-03T10:00:00+00:00",
  updated_at: null, started_at: null, finished_at: null, error_category: null, error_message: null,
  lease: { held: false, owner: null, expires_at: null, heartbeat_at: null, stale: false }, waiting_for_retry: false,
  payload_summary: { label: "Console check" }, can_retry: false, can_cancel: true, ...over });
const FAILED = JOB({ public_id: "b".repeat(32), state: "failed", attempts: 2, error_category: "configuration_error",
  error_message: "A required integration is not configured or was rejected.", can_retry: true, can_cancel: false, finished_at: "2026-10-03T10:05:00+00:00" });
const STALE = JOB({ public_id: "c".repeat(32), state: "running", attempts: 1, can_cancel: false,
  lease: { held: true, owner: "w123", expires_at: "2026-10-03T10:00:30+00:00", heartbeat_at: "2026-10-03T10:00:00+00:00", stale: true } });
const DIAG = (queued = 1, seen = 1) => ({
  queue: { queued, running: 1, failed: 1, succeeded: 3, cancelled: 0, retry_waiting: 0, stale_leases: 1, oldest_ready_age_seconds: 42 },
  by_type: [], workers: { seen_recently: seen, last_seen_at: seen ? "2026-10-03T10:00:00+00:00" : null, stale_after_seconds: 60, items: [] } });

beforeEach(() => {
  mockPerms = ["platform.jobs.read", "platform.jobs.manage"];
  list.mockResolvedValue({ items: [JOB(), FAILED, STALE], total: 60, page: 1, page_size: 25 });
  one.mockResolvedValue({ ...FAILED, audit: [{ event_type: "admin.job_retry_requested", result: "success", actor_user_id: 1, request_id: "req-9", created_at: null, context: {} }] });
  diag.mockResolvedValue(DIAG());
  types.mockResolvedValue([{ job_type: "diagnostic_noop", label: "Operational diagnostic (no-op)", max_attempts: 2, manual_retry: true, cancellable_when_queued: true, idempotency: "x" }]);
  enqueue.mockResolvedValue({ job: JOB(), created: true });
  retry.mockResolvedValue({ ...FAILED, state: "queued", can_retry: false, can_cancel: true });
  cancel.mockResolvedValue(JOB({ state: "cancelled", can_cancel: false }));
});
afterEach(() => vi.clearAllMocks());

describe("Jobs queue", () => {
  it("shows states as text, attempts as 'n of m', stale lease and failure category - never a payload", async () => {
    render(<JobsView />);
    const failed = (await screen.findByText("b".repeat(32))).closest("tr") as HTMLElement;
    expect(within(failed).getByText("Failed")).toBeInTheDocument();
    expect(within(failed).getByText("2 of 2")).toBeInTheDocument();
    expect(within(failed).getByText("Configuration problem")).toBeInTheDocument();
    const stale = screen.getByText("c".repeat(32)).closest("tr") as HTMLElement;
    expect(within(stale).getByText("Running (lease expired)")).toBeInTheDocument();
    expect(screen.queryByText(/Console check/)).not.toBeInTheDocument();       // summary only on the detail page
    expect(screen.getByText(/Job input is never shown|Payloads are never shown here/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Job list" })).toBeInTheDocument();
  });

  it("filters server-side and resets to page 1, with labelled controls", async () => {
    const user = userEvent.setup();
    render(<JobsView />);
    await screen.findByText("b".repeat(32));
    await user.selectOptions(screen.getByLabelText("State"), "failed");
    await user.type(screen.getByLabelText("Job reference"), "abc");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith({ state: "failed", q: "abc", page: 1, page_size: 25 }));
  });

  it("paginates", async () => {
    const user = userEvent.setup();
    render(<JobsView />);
    await screen.findByText("b".repeat(32));
    await user.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith({ page: 2, page_size: 25 }));
  });

  it("warns that queued jobs will not run when no worker has reported, and never infers worker health from the queue", async () => {
    diag.mockResolvedValue(DIAG(5, 0));
    render(<JobsView />);
    expect(await screen.findByText(/No worker has reported recently/)).toBeInTheDocument();
    expect(screen.getByText(/Queue size never implies a healthy worker/)).toBeInTheDocument();
  });

  it("queues the diagnostic job only after confirmation, for a manage role", async () => {
    const user = userEvent.setup();
    render(<JobsView />);
    await user.click(await screen.findByRole("button", { name: "Queue diagnostic job" }));
    expect(enqueue).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Queue job" }));
    await waitFor(() => expect(enqueue).toHaveBeenCalledWith("diagnostic_noop", { label: "Console check" }));
    expect(await screen.findByText(/A worker must pick it up/)).toBeInTheDocument();
  });

  it("a read-only role has no mutation controls", async () => {
    mockPerms = ["platform.jobs.read"];
    render(<JobsView />);
    await screen.findByText("b".repeat(32));
    expect(screen.queryByRole("button", { name: "Queue diagnostic job" })).not.toBeInTheDocument();
  });

  it("is hidden entirely without the read permission (permission-derived, no role names)", () => {
    mockPerms = ["platform.users.read"];
    render(<JobsView />);
    expect(list).not.toHaveBeenCalled();
    expect(readFileSync("components/admin/JobsView.tsx", "utf8")).not.toMatch(/platform_admin|operations_admin|platform_role/);
  });
});

describe("Job detail", () => {
  it("shows safe sections, a typed summary and no raw payload viewer", async () => {
    render(<JobDetailView id={"b".repeat(32)} />);
    expect(await screen.findByRole("heading", { name: "Execution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Input summary" })).toBeInTheDocument();
    expect(screen.getByText("Console check")).toBeInTheDocument();
    expect(screen.getByText(/Raw job input is never displayed/)).toBeInTheDocument();
    expect(screen.getByText("A required integration is not configured or was rejected.")).toBeInTheDocument();
    expect(screen.queryByText(/payload_json|stack|traceback/i)).not.toBeInTheDocument();
    expect(screen.getByText(/job retry requested/)).toBeInTheDocument();
  });

  it("retries a failed job only after confirmation and shows the new state", async () => {
    const user = userEvent.setup();
    render(<JobDetailView id={"b".repeat(32)} />);
    await user.click(await screen.findByRole("button", { name: "Retry job" }));
    expect(retry).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Retry job" }));
    await waitFor(() => expect(retry).toHaveBeenCalledWith("b".repeat(32)));
    expect(await screen.findByText("Job queued for another run.")).toBeInTheDocument();
  });

  it("offers cancel only for a queued job and never for a running one", async () => {
    one.mockResolvedValue({ ...JOB(), audit: [] });
    const user = userEvent.setup();
    const { unmount } = render(<JobDetailView id={"a".repeat(32)} />);
    expect(await screen.findByRole("button", { name: "Cancel queued job" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry job" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel queued job" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancel job" }));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith("a".repeat(32)));
    unmount();
    one.mockResolvedValue({ ...STALE, audit: [] });
    render(<JobDetailView id={"c".repeat(32)} />);
    expect(await screen.findByText(/The lease has expired/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Cancel/ })).not.toBeInTheDocument();
  });

  it("a read-only role sees no Retry or Cancel", async () => {
    mockPerms = ["platform.jobs.read"];
    render(<JobDetailView id={"b".repeat(32)} />);
    await screen.findByRole("heading", { name: "Execution" });
    expect(screen.queryByRole("button", { name: "Retry job" })).not.toBeInTheDocument();
  });
});
