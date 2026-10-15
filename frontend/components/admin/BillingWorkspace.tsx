"use client";

import { useState } from "react";
import { BillingOperationsView } from "./BillingOperationsView";
import { BillingView } from "./BillingView";
import { btn } from "./ui";

/** The Billing destination: provider billing operations (verified local state) and the W10.5 mock records (simulated metadata), kept visibly separate. */
export function BillingWorkspace() {
  const [tab, setTab] = useState<"operations" | "mock">("operations");
  return (
    <div className="grid gap-4">
      <nav aria-label="Billing areas" className="flex flex-wrap gap-2">
        <button type="button" className={btn} aria-pressed={tab === "operations"} onClick={() => setTab("operations")} data-testid="area-operations">Provider operations</button>
        <button type="button" className={btn} aria-pressed={tab === "mock"} onClick={() => setTab("mock")} data-testid="area-mock">Mock records</button>
      </nav>
      {tab === "operations" ? <BillingOperationsView /> : <BillingView />}
    </div>
  );
}
