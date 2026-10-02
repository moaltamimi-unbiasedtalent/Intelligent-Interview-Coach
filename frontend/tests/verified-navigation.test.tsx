import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NAVIGATION_VERIFY_MS, verifyNavigation } from "@/lib/navigation/verified";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));
// next/link renders an anchor and forwards onClick; the real Link also navigates, which we model as "nothing".
vi.mock("next/link", () => ({
  default: ({ href, onClick, children, ...rest }: any) => (
    <a href={href} onClick={(e) => { onClick?.(e); e.preventDefault(); }} {...rest}>{children}</a>
  ),
}));

import VerifiedLink from "@/components/ui/VerifiedLink";

beforeEach(() => {
  vi.useFakeTimers();
  push.mockReset();
});
afterEach(() => vi.useRealTimers());

function harness(initial = "/prepare") {
  let path = initial;
  const hardNavigate = vi.fn();
  const router = { push: vi.fn() };
  return {
    router, hardNavigate, setPath: (p: string) => { path = p; },
    start: (target: string) => verifyNavigation(router, target, { getPathname: () => path, hardNavigate }),
  };
}
const tick = (n = 1) => act(() => { vi.advanceTimersByTime(NAVIGATION_VERIFY_MS * n); });

describe("verifyNavigation", () => {
  it("does nothing when the first soft navigation landed", () => {
    const h = harness();
    h.start("/review");
    h.setPath("/review");
    tick(3);
    expect(h.router.push).not.toHaveBeenCalled();
    expect(h.hardNavigate).not.toHaveBeenCalled();
  });

  it("retries the soft push once when the first navigation was dropped, then stops when it lands", () => {
    const h = harness();
    h.start("/review");
    tick();
    expect(h.router.push).toHaveBeenCalledTimes(1);
    expect(h.router.push).toHaveBeenCalledWith("/review");
    h.setPath("/review");
    tick(3);
    expect(h.router.push).toHaveBeenCalledTimes(1);
    expect(h.hardNavigate).not.toHaveBeenCalled();
  });

  it("falls back to exactly one hard navigation when both soft attempts are lost", () => {
    const h = harness();
    h.start("/review");
    tick(6);
    expect(h.router.push).toHaveBeenCalledTimes(1);
    expect(h.hardNavigate).toHaveBeenCalledTimes(1);
    expect(h.hardNavigate).toHaveBeenCalledWith("/review");
  });

  it("never fights a different navigation: a pathname change to anywhere ends verification", () => {
    const h = harness();
    h.start("/review");
    h.setPath("/sources");
    tick(6);
    expect(h.router.push).not.toHaveBeenCalled();
    expect(h.hardNavigate).not.toHaveBeenCalled();
  });

  it("ignores same-page links and uses push (history preserved), never replace", () => {
    const h = harness("/review");
    h.start("/review?tab=1");
    tick(6);
    expect(h.router.push).not.toHaveBeenCalled();
    const h2 = harness();
    h2.start("/review");
    tick();
    expect(Object.keys(h2.router)).toEqual(["push"]);
  });

  it("cleanup cancels the verification", () => {
    const h = harness();
    const stop = h.start("/review");
    stop();
    tick(6);
    expect(h.router.push).not.toHaveBeenCalled();
    expect(h.hardNavigate).not.toHaveBeenCalled();
  });
});

describe("VerifiedLink", () => {
  it("renders a normal anchor with the href and recovers a dropped plain click", () => {
    Object.defineProperty(window, "location", { value: { pathname: "/prepare", assign: vi.fn() }, writable: true });
    const onClick = vi.fn();
    render(<VerifiedLink href="/review" onClick={onClick}>Review</VerifiedLink>);
    const a = screen.getByRole("link", { name: "Review" });
    expect(a).toHaveAttribute("href", "/review");
    fireEvent.click(a);
    expect(onClick).toHaveBeenCalledTimes(1);
    tick();
    expect(push).toHaveBeenCalledWith("/review");
    tick(2);
    expect(window.location.assign).toHaveBeenCalledWith("/review");
  });

  it("does not verify modified clicks, external links or target=_blank", () => {
    Object.defineProperty(window, "location", { value: { pathname: "/prepare", assign: vi.fn() }, writable: true });
    render(
      <>
        <VerifiedLink href="/a">mod</VerifiedLink>
        <VerifiedLink href="https://example.com">ext</VerifiedLink>
        <VerifiedLink href="/b" target="_blank">blank</VerifiedLink>
      </>,
    );
    fireEvent.click(screen.getByText("mod"), { ctrlKey: true });
    fireEvent.click(screen.getByText("ext"));
    fireEvent.click(screen.getByText("blank"));
    tick(6);
    expect(push).not.toHaveBeenCalled();
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});
