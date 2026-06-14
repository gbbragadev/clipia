'use client'

import { useEffect, useState } from 'react'
import { CinematicSection } from './ui/CinematicSection'
import { AnimatedCounter } from './ui/AnimatedCounter'

export default function SocialProofBar() {
  const [totalVideos, setTotalVideos] = useState(500)

  useEffect(() => {
    fetch('/api/v1/public/stats')
      .then((r) => r.json())
      .then((data) => {
        if (data.total_videos && data.total_videos > 0) {
          setTotalVideos(data.total_videos)
        }
      })
      .catch(() => {})
  }, [])

  return (
    <CinematicSection background="none" spacing="md" className="border-b border-white/5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 sm:gap-10 md:gap-8 divide-y md:divide-y-0 md:divide-x divide-white/10">
        <AnimatedCounter value={totalVideos} suffix="+" label="Vídeos criados" />
        <AnimatedCounter value={5} suffix="" label="Estilos de legenda animada" />
        <AnimatedCounter value={4} suffix="" label="Vozes pt-BR (IA)" />
      </div>
    </CinematicSection>
  )
}
