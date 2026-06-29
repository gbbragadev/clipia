import { useReducedMotion } from "motion/react";
import type { Variants, Transition } from "motion/react";

/**
 * Tokens de motion centralizados (Fase 0). Use estes em vez de
 * `transition-all .2s` solto ou easings ad-hoc — mantém a fluidez coesa
 * entre todas as superfícies (landing, dashboard, editor).
 */

/** easeOutExpo — desacelera no final, sensação cinematográfica. */
export const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const DURATIONS = {
  fast: 0.18,
  normal: 0.32,
  slow: 0.6,
} as const;

/** Spring padronizado pra CTAs/taps — responsivo, não-bouncy. */
export const SPRING: Transition = {
  type: "spring",
  stiffness: 380,
  damping: 30,
  mass: 0.8,
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: DURATIONS.normal, ease: EASE } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: DURATIONS.normal, ease: EASE } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: { duration: DURATIONS.normal, ease: EASE } },
};

/** Container pai para stagger de filhos (cards, listas). */
export const staggerContainer = (stagger = 0.08, delayChildren = 0): Variants => ({
  hidden: {},
  visible: { transition: { staggerChildren: stagger, delayChildren } },
});

/**
 * True quando o usuário prefere motion reduzido. Use para pular animações
 * JS (counters, canvas) que a media query CSS global do globals.css não cobre.
 */
export function useReducedMotionState(): boolean {
  return useReducedMotion() ?? false;
}
