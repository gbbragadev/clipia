'use client'

import { Coins } from 'lucide-react'
import type { ReactNode } from 'react'

/** Chip de custo — guardrail do DESIGN.md: TODA ação paga declara o custo ANTES
 * do clique, no mesmo formato, em todo o editor. */
export function CostChip({ children, tone = 'warn' }: { children: ReactNode; tone?: 'warn' | 'free' }) {
  const styles =
    tone === 'free'
      ? { color: 'var(--color-mint)', background: 'rgba(67,224,173,0.08)', border: '1px solid rgba(67,224,173,0.25)' }
      : { color: '#fbbf24', background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)' }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium"
      style={styles}
    >
      <Coins size={12} aria-hidden />
      {children}
    </span>
  )
}
