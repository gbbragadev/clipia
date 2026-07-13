"use client";
import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ATTRIBUTION_KEYS,
  getStoredAttribution,
  type StoredAttribution,
} from "@/hooks/useUTM";
import type { SelectedPackage } from "@/lib/package-intent";
import {
  AB_DEFAULTS,
  FREE_CLAIM,
  SITE,
  type AbSection,
  type AbVariant,
} from "./data";

/**
 * Variantes de headline trocáveis SEM redeploy: `public/ab/headlines.json` é
 * servido do disco em produção, então editar o arquivo troca a copy ao vivo.
 * O HTML estático (SEO) sempre renderiza a variante A; a variante sorteada é
 * aplicada no cliente e viaja no CTA via utm_content (medição por variante).
 */
interface AbFile {
  knobs?: { showBonusBadge?: boolean; freeClaim?: string };
  sections?: Partial<Record<AbSection, Partial<Record<AbVariant, string>>>>;
}

const VARIANTS: AbVariant[] = ["A", "B", "C"];
const STORAGE_KEY = "clipia_ab";

interface AbContextValue {
  variant: AbVariant;
  headline: (section: AbSection) => string;
  signup: (placement: string, selectedPackage?: SelectedPackage) => string;
  showBonusBadge: boolean;
  freeClaim: string;
}

const AbContext = createContext<AbContextValue | null>(null);

function readAttribution(): StoredAttribution {
  if (typeof window === "undefined") return {};
  const current = new URLSearchParams(window.location.search);
  const stored = getStoredAttribution();
  const attribution: StoredAttribution = { ...stored };
  for (const key of ATTRIBUTION_KEYS) {
    const value = current.get(key) || stored[key];
    if (value) attribution[key] = value;
  }
  attribution.referral_code = current.get("ref") || stored.referral_code;
  return attribution;
}

export function AbProvider({ children }: { children: ReactNode }) {
  const [variant, setVariant] = useState<AbVariant>("A");
  const [file, setFile] = useState<AbFile | null>(null);
  const [attribution, setAttribution] = useState<StoredAttribution>({});

  useEffect(() => {
    let v: AbVariant | null = null;
    try {
      v = localStorage.getItem(STORAGE_KEY) as AbVariant | null;
      if (!v || !VARIANTS.includes(v)) {
        v = VARIANTS[Math.floor(Math.random() * VARIANTS.length)];
        localStorage.setItem(STORAGE_KEY, v);
      }
    } catch {
      v = "A";
    }
    setVariant(v);
    setAttribution(readAttribution());

    fetch("/ab/headlines.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: AbFile | null) => d && setFile(d))
      .catch(() => {}); // sem o arquivo, os defaults embutidos valem
  }, []);

  const value = useMemo<AbContextValue>(() => {
    const headline = (section: AbSection): string =>
      file?.sections?.[section]?.[variant] ?? AB_DEFAULTS[section][variant];

    const signup = (placement: string, selectedPackage?: SelectedPackage): string => {
      const params = new URLSearchParams();
      if (selectedPackage) params.set("selected_package", selectedPackage);
      for (const key of ATTRIBUTION_KEYS) {
        if (attribution[key]) params.set(key, attribution[key]);
      }
      if (attribution.referral_code) params.set("ref", attribution.referral_code);
      params.set("placement", placement);
      params.set("ab_variant", variant.toLowerCase());
      return `${SITE.signup}?${params.toString()}`;
    };

    return {
      variant,
      headline,
      signup,
      showBonusBadge: file?.knobs?.showBonusBadge ?? true,
      freeClaim: file?.knobs?.freeClaim ?? FREE_CLAIM,
    };
  }, [attribution, file, variant]);

  return createElement(AbContext.Provider, { value }, children);
}

export function useAb(): AbContextValue {
  const value = useContext(AbContext);
  if (!value) throw new Error("useAb must be used within AbProvider");
  return value;
}
