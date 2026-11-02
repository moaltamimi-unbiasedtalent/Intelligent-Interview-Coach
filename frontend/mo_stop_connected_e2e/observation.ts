declare global { interface Window { __moStopSseObservation?: () => unknown } }

/** Test-only observation: retain fixed event-header counters, never SSE data lines. */
export function createSseHeaderObserver() {
  const kinds = ["run", "progress", "stopping", "result", "error"] as const;
  const counts = { run: 0, progress: 0, stopping: 0, result: 0, error: 0 };
  const prefix = [101, 118, 101, 110, 116, 58]; // ASCII event:
  let prefixPosition = 0, tokenPosition = 0, lineBytes = 0, total = 0;
  let candidates = kinds.map(() => true), ignoreLine = false, leadingSpace = true, overflow = false;
  function finishLine() {
    if (!ignoreLine && prefixPosition === prefix.length) {
      const found = kinds.findIndex((kind, index) => candidates[index] && tokenPosition === kind.length);
      if (found >= 0) {
        if (total < 100) { counts[kinds[found]]++; total++; } else overflow = true;
      }
    }
    prefixPosition = 0; tokenPosition = 0; lineBytes = 0;
    candidates = kinds.map(() => true); ignoreLine = false; leadingSpace = true;
  }
  return {
    feed(bytes: Uint8Array) {
      for (const byte of bytes) {
        if (byte === 10 || byte === 13) { finishLine(); continue; }
        if (ignoreLine) continue;
        lineBytes++;
        if (lineBytes > 64) { ignoreLine = true; continue; }
        if (prefixPosition < prefix.length) {
          if (byte === prefix[prefixPosition]) prefixPosition++; else ignoreLine = true;
        } else {
          if (leadingSpace && byte === 32) continue;
          leadingSpace = false;
          candidates = candidates.map((candidate, index) => candidate && kinds[index].charCodeAt(tokenPosition) === byte);
          tokenPosition++;
          if (!candidates.some(Boolean)) ignoreLine = true;
        }
      }
    },
    snapshot() { return { ...counts, total, overflow }; },
  };
}

// Serialized by Playwright as an init script. Return the exact original Response;
// only its clone is read by this independent, bounded header observer.
export function installMoStopObservation(create: typeof createSseHeaderObserver) {
  const observer = create();
  const original = window.fetch;
  let readError = false;
  Object.defineProperty(window, "__moStopSseObservation", {
    value: () => ({ ...observer.snapshot(), read_error: readError }),
    writable: false,
  });
  window.fetch = async function (...args: Parameters<typeof fetch>) {
    const response = await original.apply(this, args);
    if (response.headers.get("content-type")?.startsWith("text/event-stream")) {
      try {
        const reader = response.clone().body?.getReader();
        if (!reader) readError = true;
        else void (async () => {
          try {
            while (true) {
              const item = await reader.read();
              if (item.done) break;
              observer.feed(item.value);
            }
          } catch { readError = true; }
          finally { reader.releaseLock(); }
        })();
      } catch { readError = true; }
    }
    return response;
  };
}

export function realProgressObserved(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  if (Object.keys(v).sort().join(",") !== "error,overflow,progress,read_error,result,run,stopping,total") return false;
  const keys = ["run", "progress", "stopping", "result", "error"];
  if (!keys.every(key => typeof v[key] === "number" && Number.isInteger(v[key]) && (v[key] as number) >= 0 && (v[key] as number) <= 100)) return false;
  const sum = keys.reduce((total, key) => total + (v[key] as number), 0);
  return v.total === sum && sum <= 100 && v.overflow === false && v.read_error === false && (v.progress as number) > 0;
}

export function stoppingStreamObserved(value: unknown): boolean {
  if (!realProgressObserved(value)) return false;
  const v = value as Record<string, unknown>;
  return v.stopping === 1 && v.error === 0;
}

export function completeStreamObserved(value: unknown): boolean {
  if (!stoppingStreamObserved(value)) return false;
  const v = value as Record<string, unknown>;
  return v.run === 1 && v.result === 1;
}
