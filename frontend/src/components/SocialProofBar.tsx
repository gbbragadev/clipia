'use client'

import { CinematicSection } from './ui/CinematicSection'
import { AnimatedCounter } from './ui/AnimatedCounter'

export default function SocialProofBar() {
  return (
    <CinematicSection background="none" spacing="md" className="border-b border-white/5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8 divide-y md:divide-y-0 md:divide-x divide-white/10">
        <AnimatedCounter value={500} suffix="+" label="Vídeos criados" />
        <AnimatedCounter value={2} suffix="min" label="Tempo médio" />
        <AnimatedCounter value={3} suffix="" label="Vozes pt-BR" />
      </div>
    </CinematicSection>
  )
}
