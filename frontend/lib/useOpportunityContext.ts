"use client";

/**
 * Read an optional `?opportunity=<id>` from the URL and load that owner-scoped Opportunity (P10B
 * Wave 6), so Prepare / Practice / Company research can PRE-POPULATE their inputs from it. The
 * candidate can still edit every field: Opportunity context is an initial value, never a silent
 * override of an explicit session choice (precedence: explicit session > opportunity > account >
 * default). A foreign/unknown id resolves to null (the server 404s it) and simply prefills nothing.
 */

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { api } from "@/lib/api/client";
import type { OpportunityOverview } from "@/lib/api/types";

export interface OpportunityContextState {
  opportunity: OpportunityOverview | null;
  loading: boolean;
}

export function useOpportunityContext(): OpportunityContextState {
  const params = useSearchParams();
  const raw = params?.get("opportunity") ?? null;
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  const [opportunity, setOpportunity] = useState<OpportunityOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(id !== null);

  useEffect(() => {
    if (id === null) {
      setOpportunity(null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    api.opportunities
      .get(id)
      .then((o) => {
        if (active) setOpportunity(o);
      })
      .catch(() => {
        if (active) setOpportunity(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);

  return { opportunity, loading };
}
