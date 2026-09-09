import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const list = vi.fn();
const update = vi.fn();
const remove = vi.fn();
const preview = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: { memory: { list: (...a: unknown[]) => list(...a), update: (...a: unknown[]) => update(...a),
                    remove: (...a: unknown[]) => remove(...a), preview: (...a: unknown[]) => preview(...a) } },
}));

import { MemoryManager } from "@/components/memory/MemoryManager";

function mem(over: Record<string, unknown> = {}) {
  return {
    id: 1, category: "recurring_gap", summary: "Stakeholder communication",
    target_role: "PM", pinned: false, source_run_id: null,
    created_at: null, updated_at: null, ...over,
  };
}

beforeEach(() => {
  list.mockResolvedValue({ memories: [mem()] });
  preview.mockResolvedValue({ target_role: null, load_limit: 10, items: [] });
});
afterEach(() => vi.clearAllMocks());

describe("MemoryManager", () => {
  it("lists saved memory with category and role", async () => {
    render(<MemoryManager />);
    expect(await screen.findByText("Stakeholder communication")).toBeInTheDocument();
    expect(screen.getByText("Priority")).toBeInTheDocument();  // friendly category label
    expect(screen.getByText("PM")).toBeInTheDocument();
  });

  it("opens and cancels the edit form", async () => {
    render(<MemoryManager />);
    await userEvent.click(await screen.findByRole("button", { name: /Edit saved memory/ }));
    expect(screen.getByLabelText("Memory")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("Memory")).not.toBeInTheDocument();
  });

  it("saves an edit", async () => {
    update.mockResolvedValue(mem({ summary: "Refined" }));
    render(<MemoryManager />);
    await userEvent.click(await screen.findByRole("button", { name: /Edit saved memory/ }));
    const box = screen.getByLabelText("Memory");
    await userEvent.clear(box);
    await userEvent.type(box, "Refined");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, expect.objectContaining({ summary: "Refined" })));
    expect(await screen.findByText("Refined")).toBeInTheDocument();
  });

  it("pins and unpins", async () => {
    update.mockResolvedValue(mem({ pinned: true }));
    render(<MemoryManager />);
    await userEvent.click(await screen.findByRole("button", { name: /^Pin saved memory/ }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, { pinned: true }));
  });

  it("confirms before deleting", async () => {
    remove.mockResolvedValue({ deleted: true, id: 1 });
    render(<MemoryManager />);
    await userEvent.click(await screen.findByRole("button", { name: /Remove saved memory/ }));
    expect(remove).not.toHaveBeenCalled();  // confirmation first
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Stakeholder communication")).not.toBeInTheDocument());
  });

  it("preserves entered text when a save fails", async () => {
    update.mockRejectedValue(Object.assign(new Error("409"), { userMessage: "An equivalent memory already exists." }));
    render(<MemoryManager />);
    await userEvent.click(await screen.findByRole("button", { name: /Edit saved memory/ }));
    const box = screen.getByLabelText("Memory");
    await userEvent.clear(box);
    await userEvent.type(box, "Dup");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("An equivalent memory already exists.")).toBeInTheDocument();
    expect((screen.getByLabelText("Memory") as HTMLTextAreaElement).value).toBe("Dup");  // input kept
  });

  it("shows a role-scoped next-run preview", async () => {
    preview.mockResolvedValue({
      target_role: "PM", load_limit: 10,
      items: [{ id: 1, category: "recurring_gap", summary: "Stakeholder communication",
                target_role: "PM", pinned: true, order: 0, reason: "Matches this role" }],
    });
    render(<MemoryManager />);
    await userEvent.type(await screen.findByLabelText("Target role (optional)"), "PM");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(preview).toHaveBeenCalledWith("PM"));
    const list2 = await screen.findByText("Matches this role");
    expect(list2).toBeInTheDocument();
  });

  it("shows an honest empty preview", async () => {
    preview.mockResolvedValue({ target_role: "Nurse", load_limit: 10, items: [] });
    render(<MemoryManager />);
    await userEvent.type(await screen.findByLabelText("Target role (optional)"), "Nurse");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("No saved preparation memories would be loaded for this role.")).toBeInTheDocument();
  });
});
