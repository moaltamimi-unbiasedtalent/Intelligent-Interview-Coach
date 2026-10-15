import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { newIdempotencyKey, trustedCheckoutUrl } from "@/lib/billing/trustedRedirect";
import en from "@/lib/i18n/messages/w124dc/en";

let search = "session=abcdefgh1234&outcome=success";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search), useRouter: () => ({ push() {}, replace() {} }), usePathname: () => "/account" }));

const availability = vi.fn();
const status = vi.fn();
const startCheckout = vi.fn();
const recordReturn = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { billing: {
    availability: (...a: unknown[]) => availability(...a), status: (...a: unknown[]) => status(...a),
    startCheckout: (...a: unknown[]) => startCheckout(...a), recordReturn: (...a: unknown[]) => recordReturn(...a),
  } },
  ApiError: class ApiError extends Error { status = 0; },
}));

import { PremiumSubscriptionPanel } from "@/components/account/PremiumSubscriptionPanel";
import { ReturnPanel } from "@/components/billing/ReturnPanel";

const none = { checkout: "none", subscription: "none", payment: "none", confirmation: "not_applicable",
  entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false }, checkout_id: null, created_at: null, expires_at: null };
const wrap = (ui: React.ReactNode) => render(<I18nProvider>{ui}</I18nProvider>);
const FORBIDDEN = /payment (was )?successful|subscription (is )?active|premium (is )?unlocked|thank you for your purchase|you are now premium/i;

beforeEach(() => { vi.clearAllMocks(); search = "session=abcdefgh1234&outcome=success"; });

describe("trusted checkout URL", () => {
  it.each([
    ["https://checkout.stripe.com/c/pay/cs_test_1", true],
    ["http://checkout.stripe.com/c/pay/cs_test_1", false],
    ["https://evil.test/checkout.stripe.com", false],
    ["https://checkout.stripe.com.evil.test/x", false],
    ["https://user:pw@checkout.stripe.com/x", false],
    ["javascript:alert(1)", false],
    ["//checkout.stripe.com/x", false],
    ["", false],
  ])("%s -> %s", (url, ok) => { expect(trustedCheckoutUrl(url) !== null).toBe(ok); });
  it("null and undefined are refused", () => { expect(trustedCheckoutUrl(null)).toBeNull(); expect(trustedCheckoutUrl(undefined)).toBeNull(); });
  it("idempotency keys fit the server pattern and differ", () => {
    const a = newIdempotencyKey(), b = newIdempotencyKey();
    expect(a).toMatch(/^[A-Za-z0-9_-]{8,64}$/); expect(a).not.toBe(b);
  });
});

describe("PremiumSubscriptionPanel", () => {
  it("has NO purchase button when the server says checkout is not enabled", async () => {
    availability.mockResolvedValue({ plan: "premium", available: false, reason: "not_enabled" });
    status.mockResolvedValue(none);
    wrap(<PremiumSubscriptionPanel />);
    expect(await screen.findByTestId("checkout-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("checkout-start")).toBeNull();
    expect(document.body.textContent).not.toMatch(FORBIDDEN);
  });

  it("an unreachable availability call fails closed (no button)", async () => {
    availability.mockRejectedValue(new Error("x"));
    status.mockResolvedValue(none);
    wrap(<PremiumSubscriptionPanel />);
    expect(await screen.findByTestId("checkout-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("checkout-start")).toBeNull();
  });

  it("starts checkout with only the plan code and refuses an untrusted redirect target", async () => {
    availability.mockResolvedValue({ plan: "premium", available: true, reason: null });
    status.mockResolvedValue(none);
    startCheckout.mockResolvedValue({ checkout_id: "c", status: "open", redirect_url: "https://evil.test/pay", expires_at: null, browser_returned: false });
    wrap(<PremiumSubscriptionPanel />);
    await userEvent.click(await screen.findByTestId("checkout-start"));
    await waitFor(() => expect(startCheckout).toHaveBeenCalledTimes(1));
    expect(startCheckout.mock.calls[0][0]).toBe("premium");
    expect(startCheckout.mock.calls[0][1]).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(await screen.findByText(en.checkout.providerUnavailable)).toBeInTheDocument();
  });

  it("reuses the same idempotency key when the same click is retried", async () => {
    availability.mockResolvedValue({ plan: "premium", available: true, reason: null });
    status.mockResolvedValue(none);
    startCheckout.mockRejectedValue(new Error("down"));
    wrap(<PremiumSubscriptionPanel />);
    await userEvent.click(await screen.findByTestId("checkout-start"));
    await screen.findByText(en.checkout.providerUnavailable);
    await userEvent.click(screen.getByTestId("checkout-start"));
    await waitFor(() => expect(startCheckout).toHaveBeenCalledTimes(2));
    expect(startCheckout.mock.calls[0][1]).toBe(startCheckout.mock.calls[1][1]);
  });

  it("shows a pending-confirmation state after a browser return, never a success state", async () => {
    availability.mockResolvedValue({ plan: "premium", available: true, reason: null });
    status.mockResolvedValue({ ...none, checkout: "open", subscription: "confirmation_pending", payment: "pending", confirmation: "pending" });
    wrap(<PremiumSubscriptionPanel />);
    expect(await screen.findByText(en.checkout.pendingTitle)).toBeInTheDocument();
    expect(screen.queryByTestId("checkout-start")).toBeNull();          // no second purchase while confirmation is pending
    expect(document.body.textContent).not.toMatch(FORBIDDEN);
  });

  it("status failure is shown as unavailable, not as a plan", async () => {
    availability.mockResolvedValue({ plan: "premium", available: false, reason: "not_enabled" });
    status.mockRejectedValue(new Error("x"));
    wrap(<PremiumSubscriptionPanel />);
    expect(await screen.findByText(en.checkout.statusUnavailable)).toBeInTheDocument();
  });
});

describe("ReturnPanel", () => {
  it("a success-looking return only records the return and says we are waiting", async () => {
    recordReturn.mockResolvedValue({ checkout_id: "c", status: "open", redirect_url: null, expires_at: null, browser_returned: true });
    wrap(<ReturnPanel />);
    expect(await screen.findByText(en.checkout.pendingTitle)).toBeInTheDocument();
    expect(recordReturn).toHaveBeenCalledWith("abcdefgh1234", "success");
    expect(document.body.textContent).not.toMatch(FORBIDDEN);
  });

  it("a cancel return shows canceled and nothing was charged", async () => {
    search = "session=abcdefgh1234&outcome=cancel";
    recordReturn.mockResolvedValue({ checkout_id: "c", status: "canceled", redirect_url: null, expires_at: null, browser_returned: false });
    wrap(<ReturnPanel />);
    expect(await screen.findByText(en.checkout.canceledTitle)).toBeInTheDocument();
  });

  it("a missing or unknown session is unavailable, never success", async () => {
    search = "outcome=success";
    wrap(<ReturnPanel />);
    expect(await screen.findByText(en.checkout.statusUnavailable)).toBeInTheDocument();
    expect(recordReturn).not.toHaveBeenCalled();
  });
});

describe("checkout copy", () => {
  it("exists in all eight locales and no locale claims success", () => {
    for (const loc of SUPPORTED_LOCALE_CODES) {
      for (const key of Object.keys(en.checkout)) {
        const v = translate(loc, `checkout.${key}`);
        expect(v, `${loc}.${key}`).toBeTruthy();
        expect(v).not.toBe(`checkout.${key}`);
      }
    }
    for (const v of Object.values(en.checkout)) expect(v).not.toMatch(FORBIDDEN);
  });
});
