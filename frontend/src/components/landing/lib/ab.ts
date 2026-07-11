"use client";
import { useEffect, useState } from "react";
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

export function useAb() {
  const [variant, setVariant] = useState<AbVariant>("A");
  const [file, setFile] = useState<AbFile | null>(null);

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

    fetch("/ab/headlines.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: AbFile | null) => d && setFile(d))
      .catch(() => {}); // sem o arquivo, os defaults embutidos valem
  }, []);

  const headline = (section: AbSection): string =>
    file?.sections?.[section]?.[variant] ?? AB_DEFAULTS[section][variant];

  const signup = (content: string): string =>
    `${SITE.signup}?utm_source=landing&utm_medium=organic&utm_campaign=landing-conversao&utm_content=${content}-${variant.toLowerCase()}`;

  return {
    variant,
    headline,
    signup,
    showBonusBadge: file?.knobs?.showBonusBadge ?? true,
    freeClaim: file?.knobs?.freeClaim ?? FREE_CLAIM,
  };
}
