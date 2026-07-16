"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

import {
  ATTRIBUTION_KEYS,
  captureRegistrationAttribution,
  clearRegistrationAttribution,
  readRegistrationAttribution,
  readStoredAttribution,
  type AttributionKey,
  type RegistrationAttribution,
  type StoredAttribution,
} from "@/lib/registration-attribution";

export { ATTRIBUTION_KEYS };
export type { AttributionKey, StoredAttribution };

/** Captures campaign attribution while keeping the offer separate from UTM fields. */
export function useUTM() {
  const searchParams = useSearchParams();

  useEffect(() => {
    captureRegistrationAttribution(searchParams, localStorage);
  }, [searchParams]);
}

/** Read full stored attribution for first-party analytics. */
export function getStoredAttribution(): StoredAttribution {
  if (typeof window === "undefined") return {};
  return readStoredAttribution(localStorage);
}

/** Read only the attribution fields accepted by POST /auth/register. */
export function getStoredUTM(): RegistrationAttribution {
  if (typeof window === "undefined") return {};
  return readRegistrationAttribution(localStorage);
}

/** Clear attribution only after registration succeeds. */
export function clearStoredUTM() {
  if (typeof window === "undefined") return;
  clearRegistrationAttribution(localStorage);
}
