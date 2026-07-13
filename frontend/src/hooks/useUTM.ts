"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

export const ATTRIBUTION_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "utm_id",
] as const;
const AUTH_SAFE_UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign"] as const;
const REF_KEY = "ref";
const STORAGE_PREFIX = "clipia_";

export type AttributionKey = (typeof ATTRIBUTION_KEYS)[number];
type AuthSafeUtmKey = (typeof AUTH_SAFE_UTM_KEYS)[number];
export type StoredAttribution = Partial<Record<AttributionKey, string>> & {
  referral_code?: string;
};
type AuthSafeAttribution = Partial<Record<AuthSafeUtmKey, string>> & {
  referral_code?: string;
};

/** Captures UTM params and referral code from URL into localStorage. */
export function useUTM() {
  const searchParams = useSearchParams();

  useEffect(() => {
    for (const key of ATTRIBUTION_KEYS) {
      const value = searchParams.get(key);
      if (value) localStorage.setItem(`${STORAGE_PREFIX}${key}`, value);
    }
    const ref = searchParams.get(REF_KEY);
    if (ref) localStorage.setItem(`${STORAGE_PREFIX}ref`, ref);
  }, [searchParams]);
}

/** Read stored UTM + referral data for registration. */
export function getStoredAttribution(): StoredAttribution {
  if (typeof window === "undefined") return {};
  const result: StoredAttribution = {};
  for (const key of ATTRIBUTION_KEYS) {
    const v = localStorage.getItem(`${STORAGE_PREFIX}${key}`);
    if (v) result[key] = v;
  }
  const ref = localStorage.getItem(`${STORAGE_PREFIX}ref`);
  if (ref) result.referral_code = ref;
  return result;
}

/** Subset que o contrato atual de POST /auth/register aceita. */
export function getStoredUTM(): AuthSafeAttribution {
  const stored = getStoredAttribution();
  const result: AuthSafeAttribution = {};
  for (const key of AUTH_SAFE_UTM_KEYS) {
    if (stored[key]) result[key] = stored[key];
  }
  if (stored.referral_code) result.referral_code = stored.referral_code;
  return result;
}

/** Clear stored UTM data after registration. */
export function clearStoredUTM() {
  if (typeof window === "undefined") return;
  for (const key of ATTRIBUTION_KEYS) localStorage.removeItem(`${STORAGE_PREFIX}${key}`);
  localStorage.removeItem(`${STORAGE_PREFIX}ref`);
}
