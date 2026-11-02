import { describe, expect, it } from "vitest";
import { createSseHeaderObserver, realProgressObserved, stoppingStreamObserved, completeStreamObserved } from "../mo_stop_connected_e2e/observation";
const bytes = (text: string) => new TextEncoder().encode(text);
const withRead = <T extends object>(value: T) => ({ ...value, read_error: false });
describe("Mo Stop bounded real-SSE header observation", () => {
  it("requires an actual progress header instead of initial frontend state", () => {
    const observer = createSseHeaderObserver();
    expect(realProgressObserved(withRead(observer.snapshot()))).toBe(false);
    observer.feed(bytes("event: run\ndata: ignored\n\n"));
    expect(realProgressObserved(withRead(observer.snapshot()))).toBe(false);
    observer.feed(bytes("event: progress\ndata: ignored\n\n"));
    expect(realProgressObserved(withRead(observer.snapshot()))).toBe(true);
  });
  it("retains no data-line, credential, prompt or unknown-header canary", () => {
    const observer = createSseHeaderObserver();
    const canary = "PRIVATE_CANARY_TOKEN_EMAIL_PROMPT";
    observer.feed(bytes(`data: ${canary}\nevent: ${canary}\n: ${canary}\nevent: progress\ndata: ${canary}\n\n`));
    expect(JSON.stringify(observer.snapshot())).not.toContain(canary);
    expect(observer.snapshot()).toEqual({ run: 0, progress: 1, stopping: 0, result: 0, error: 0, total: 1, overflow: false });
  });
  it("recognizes headers across chunks and discards split data lines", () => {
    const observer = createSseHeaderObserver();
    for (const part of ["ev", "ent: pro", "gress\r", "\ndata: ev", "ent: result\n", "event: result\n"]) observer.feed(bytes(part));
    expect(observer.snapshot()).toMatchObject({ progress: 1, result: 1, total: 2 });
  });
  it("ignores unknown, malformed and oversized event headers", () => {
    const observer = createSseHeaderObserver();
    observer.feed(bytes(`events: progress\nevent: unknown\nevent:progressX\nevent: ${" ".repeat(100)}progress\nevent: stopping\n`));
    expect(observer.snapshot()).toMatchObject({ progress: 0, stopping: 1, total: 1 });
  });
  it("bounds counters and fails evidence on retention overflow", () => {
    const observer = createSseHeaderObserver();
    observer.feed(bytes("event: progress\n".repeat(101)));
    expect(observer.snapshot()).toMatchObject({ progress: 100, total: 100, overflow: true });
    expect(realProgressObserved(withRead(observer.snapshot()))).toBe(false);
  });
  it("rejects failed observation, missing fields and inconsistent counts", () => {
    const observer = createSseHeaderObserver(); observer.feed(bytes("event: progress\n"));
    const valid = withRead(observer.snapshot());
    expect(realProgressObserved(valid)).toBe(true);
    expect(realProgressObserved({ ...valid, read_error: true })).toBe(false);
    expect(realProgressObserved({ ...valid, total: 2 })).toBe(false);
    expect(realProgressObserved({ ...valid, progress: true })).toBe(false);
    expect(realProgressObserved({ ...valid, private_payload: "canary" })).toBe(false);
    const missing: Record<string, unknown> = { ...valid }; delete missing.progress;
    expect(realProgressObserved(missing)).toBe(false);
  });
});


describe("Mo Stop full-stream observation controls", () => {
  it("requires actual stopping and terminal event headers without observation failures", () => {
    const observer = createSseHeaderObserver();
    observer.feed(bytes("event: run\nevent: progress\n"));
    expect(stoppingStreamObserved(withRead(observer.snapshot()))).toBe(false);
    expect(completeStreamObserved(withRead(observer.snapshot()))).toBe(false);
    observer.feed(bytes("event: stopping\n"));
    expect(stoppingStreamObserved(withRead(observer.snapshot()))).toBe(true);
    expect(completeStreamObserved(withRead(observer.snapshot()))).toBe(false);
    observer.feed(bytes("event: result\n"));
    const complete = withRead(observer.snapshot());
    expect(completeStreamObserved(complete)).toBe(true);
    expect(completeStreamObserved({ ...complete, read_error: true })).toBe(false);
    expect(completeStreamObserved({ ...complete, overflow: true })).toBe(false);
    observer.feed(bytes("event: error\n"));
    expect(stoppingStreamObserved(withRead(observer.snapshot()))).toBe(false);
    expect(completeStreamObserved(withRead(observer.snapshot()))).toBe(false);
  });
  it("rejects duplicate or missing run, stopping and terminal classifications", () => {
    const observer = createSseHeaderObserver();
    observer.feed(bytes("event: run\nevent: progress\nevent: stopping\nevent: result\n"));
    const valid = withRead(observer.snapshot());
    for (const key of ["run", "stopping", "result"] as const) {
      expect(completeStreamObserved({ ...valid, [key]: 0, total: valid.total - 1 })).toBe(false);
      expect(completeStreamObserved({ ...valid, [key]: 2, total: valid.total + 1 })).toBe(false);
    }
  });
});
