"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign"] as const;
const REF_KEY = "ref";
const STORAGE_PREFIX = "clipia_";

/** Captures UTM params and referral code from URL into localStorage. */
export function useUTM() {
  const searchParams = useSearchParams();

  useEffect(() => {
    for (const key of UTM_KEYS) {
      const value = searchParams.get(key);
      if (value) localStorage.setItem(`${STORAGE_PREFIX}${key}`, value);
    }
    const ref = searchParams.get(REF_KEY);
    if (ref) localStorage.setItem(`${STORAGE_PREFIX}ref`, ref);
  }, [searchParams]);
}

/** Read stored UTM + referral data for registration. */
export function getStoredUTM(): {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  referral_code?: string;
} {
  if (typeof window === "undefined") return {};
  const result: Record<string, string> = {};
  for (const key of UTM_KEYS) {
    const v = localStorage.getItem(`${STORAGE_PREFIX}${key}`);
    if (v) result[key] = v;
  }
  const ref = localStorage.getItem(`${STORAGE_PREFIX}ref`);
  if (ref) result.referral_code = ref;
  return result;
}

/** Clear stored UTM data after registration. */
export function clearStoredUTM() {
  if (typeof window === "undefined") return;
  for (const key of UTM_KEYS) localStorage.removeItem(`${STORAGE_PREFIX}${key}`);
  localStorage.removeItem(`${STORAGE_PREFIX}ref`);
}
