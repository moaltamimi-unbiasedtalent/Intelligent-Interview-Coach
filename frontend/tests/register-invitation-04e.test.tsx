import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 04E: the candidate registration invitation field and the Admin invitation controls. The refusal copy is localised by the interface language and driven by the
// stable server code (never English matching); the code is read from the URL fragment, cleared from the address bar, and never stored.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  usePathname: () => "/register",
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: any) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const register = vi.fn();
const invitations = vi.fn();
const issueInvitation = vi.fn();
const revokeInvitation = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: {
      auth: { register: (...a: unknown[]) => register(...a) },
      admin: {
        invitations: (...a: unknown[]) => invitations(...a),
        issueInvitation: (...a: unknown[]) => issueInvitation(...a),
        revokeInvitation: (...a: unknown[]) => revokeInvitation(...a),
      },
    },
  };
});

import { ApiError } from "@/lib/api/errors";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { InvitationsPanel } from "@/components/admin/InvitationsPanel";
import { CATALOGS } from "@/lib/i18n/catalog";

const refusal = () => new ApiError({ kind: "forbidden", status: 403, code: "invitation_required", message: "server english text" });

beforeEach(() => {
  mockPerms = [];
  window.history.replaceState(null, "", "/register");
});
afterEach(() => vi.clearAllMocks());

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^email/i), "new@example.test");
  await user.type(screen.getByLabelText(/^password/i), "a-long-enough-pass");
  await user.click(screen.getByRole("button", { name: /create account/i }));
}

describe("registration invitation field", () => {
  it("shows a labelled invitation field and sends the code with the registration", async () => {
    register.mockResolvedValue({ message: "x" });
    const user = userEvent.setup();
    render(<RegisterForm />);
    await user.type(screen.getByLabelText(/invitation code/i), "  abc-123  ");
    await fillAndSubmit(user);
    await waitFor(() => expect(register).toHaveBeenCalledWith(expect.objectContaining({ invitation_code: "abc-123", email: "new@example.test" })));
  });

  it("sends null when the field is empty (the server decides whether one is required)", async () => {
    register.mockResolvedValue({ message: "x" });
    const user = userEvent.setup();
    render(<RegisterForm />);
    await fillAndSubmit(user);
    await waitFor(() => expect(register).toHaveBeenCalledWith(expect.objectContaining({ invitation_code: null })));
  });

  it("prefills from the URL fragment, removes it from the address bar and never writes it to storage", async () => {
    window.history.replaceState(null, "", "/register#invitation=frag-code_9");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    render(<RegisterForm />);
    await waitFor(() => expect(screen.getByLabelText(/invitation code/i)).toHaveValue("frag-code_9"));
    expect(window.location.hash).toBe("");
    expect(window.location.href).not.toContain("frag-code_9");
    expect(setItem).not.toHaveBeenCalled();
    expect(document.cookie).not.toContain("frag-code_9");
  });

  it("shows the localised uniform refusal for the stable code, never the server text", async () => {
    register.mockRejectedValue(refusal());
    const user = userEvent.setup();
    render(<RegisterForm />);
    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(CATALOGS.en.auth.invitationRequired);
    expect(document.body.textContent).not.toContain("server english text");
  });

  it("other registration errors keep their existing behaviour", async () => {
    register.mockRejectedValue(new ApiError({ kind: "validation", status: 422, code: "validation_error", message: "Enter a valid email address." }));
    const user = userEvent.setup();
    render(<RegisterForm />);
    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid email address.");
  });
});

describe("invitation copy in every catalogue locale", () => {
  it.each(["en", "de", "fr", "es", "it", "pt", "nl", "ru"] as const)("%s has the three keys, translated and free of the protected slogan", (loc) => {
    const a = (CATALOGS as unknown as Record<string, { auth: Record<string, string> }>)[loc].auth;
    for (const k of ["invitationLabel", "invitationHint", "invitationRequired"]) {
      expect(typeof a[k]).toBe("string");
      expect(a[k].length).toBeGreaterThan(8);
      expect(a[k]).not.toContain("—");
      if (loc !== "en") expect(a[k]).not.toBe((CATALOGS.en.auth as Record<string, string>)[k]);
    }
  });
});

const ROW = { id: 7, state: "pending", created_at: "2026-10-22T08:00:00", expires_at: "2026-11-05T08:00:00", redeemed_at: null, revoked_at: null, email_bound: true,
  email_hint: "j***@e***.com", issued_by_user_id: 1 };

describe("Admin invitations panel", () => {
  beforeEach(() => {
    invitations.mockResolvedValue({ items: [ROW, { ...ROW, id: 6, email_hint: null, email_bound: false, state: "redeemed", redeemed_at: "2026-10-21T10:00:00" }], total: 2, counts: { pending: 1, redeemed: 1 } });
  });

  it("lists state and masked identifiers only and offers revoke for pending rows", async () => {
    mockPerms = ["platform.users.read", "platform.users.manage"];
    revokeInvitation.mockResolvedValue({ ...ROW, state: "revoked" });
    render(<InvitationsPanel />);
    expect(await screen.findByText("j***@e***.com")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/code_hash|email_hash/);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Revoke invitation 7" }));
    expect(revokeInvitation).toHaveBeenCalledWith(7);
    expect(screen.queryByRole("button", { name: "Revoke invitation 6" })).toBeNull();
  });

  it("shows the issued link once and forgets it after Done", async () => {
    mockPerms = ["platform.users.read", "platform.users.manage"];
    issueInvitation.mockResolvedValue({ ...ROW, email_bound: false, email_hint: null, code: "plain-code", link: "https://app.example.test/register#invitation=plain-code" });
    const user = userEvent.setup();
    render(<InvitationsPanel />);
    await user.click(await screen.findByRole("button", { name: /issue invitation/i }));
    const link = await screen.findByLabelText("Invitation link");
    expect(link).toHaveValue("https://app.example.test/register#invitation=plain-code");
    expect(screen.getByText(/shown once and cannot be recovered/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByLabelText("Invitation link")).toBeNull();
    expect(document.body.textContent).not.toContain("plain-code");
  });

  it("hides issue and revoke controls from a read-only administrator", async () => {
    mockPerms = ["platform.users.read"];
    render(<InvitationsPanel />);
    expect(await screen.findByText("j***@e***.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /issue invitation/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /revoke invitation/i })).toBeNull();
  });
});
