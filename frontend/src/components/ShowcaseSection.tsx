'use client'

import { useRef, useCallback, useEffect, useState } from 'react'
import { CinematicSection } from './ui/CinematicSection'
import { GlowCard } from './ui/GlowCard'
import { PretextHeading } from './ui/PretextHeading'
import Link from 'next/link'
import { loadShowcase, type ShowcaseManifest, type ShowcaseVideo } from '@/lib/showcase'

export function ShowcaseCard({ item, featured = false }: { item: ShowcaseVideo; featured?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const card = cardRef.current
    const video = videoRef.current
    if (!card || !video) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) video.play().catch(() => {}) },
      { threshold: 0.3 },
    )
    observer.observe(card)
    return () => observer.disconnect()
  }, [])

  const handleEnter = useCallback(() => {
    const v = videoRef.current
    if (v) { v.muted = false; v.volume = 0.6; v.play().catch(() => {}) }
  }, [])
  const handleLeave = useCallback(() => { const v = videoRef.current; if (v) v.muted = true }, [])

  return (
    <GlowCard className={`h-full ${featured ? 'md:col-span-2' : ''}`}>
      <div
        ref={cardRef}
        className="w-full h-full relative cursor-pointer snap-center shrink-0"
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onTouchStart={handleEnter}
        onTouchEnd={handleLeave}
      >
        <div className="relative w-full h-full aspect-[9/16] md:aspect-auto md:min-h-[500px] overflow-hidden">
          <video
            ref={videoRef}
            autoPlay muted loop playsInline preload="metadata"
            className="w-full h-full object-cover"
            src={item.video}
          />
          {/* Badge: estilo de legenda */}
          <div className="absolute top-4 left-4 z-10">
            <span
              className="text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded-md bg-black/50 backdrop-blur-md border border-white/10"
              style={{ color: item.captionAccent }}
            >
              legenda: {item.captionStyle}
            </span>
          </div>
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#0f0b1a] via-[#0f0b1a]/80 to-transparent p-6 pt-24">
            <h3 className={`font-bold text-white leading-tight ${featured ? 'text-2xl' : 'text-lg'}`}>{item.title}</h3>
            {item.beforeScript && (
              <p className="mt-2 text-xs text-white/50 italic">Prompt: &ldquo;{item.beforeScript}&rdquo;</p>
            )}
            <span className="inline-block mt-3 text-xs px-3 py-1 rounded-full bg-white/10 text-white/80 backdrop-blur-md border border-white/5">
              {item.template}
            </span>
          </div>
        </div>
      </div>
    </GlowCard>
  )
}

export default function ShowcaseSection() {
  const [manifest, setManifest] = useState<ShowcaseManifest | null>(null)
  const [niche, setNiche] = useState<string>('all')

  useEffect(() => { loadShowcase().then(setManifest).catch(() => {}) }, [])

  if (!manifest) return null
  const videos = niche === 'all' ? manifest.videos : manifest.videos.filter((v) => v.niche === niche)

  return (
    <CinematicSection background="none" spacing="xl" reveal="fade-up" className="border-b border-white/5">
      <div className="text-center mb-10 max-w-3xl mx-auto">
        <PretextHeading text="O que a IA cria em minutos" animation="blur-focus" color="#ffffff" className="mb-6" />
        <p className="text-xl text-slate-400">
          Vídeos reais gerados e editados no ClipIA. Passe o mouse para ouvir.
        </p>
      </div>

      {/* Filtro por nicho — scroll horizontal no mobile */}
      <div className="flex gap-2 justify-start md:justify-center mb-10 overflow-x-auto px-4 snap-x [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {[{ id: 'all', label: 'Todos', icon: '✦' }, ...manifest.niches.filter((n) => manifest.videos.some((v) => v.niche === n.id))].map((n) => (
          <button
            key={n.id}
            onClick={() => setNiche(n.id)}
            className={`shrink-0 snap-start text-sm px-4 py-2 rounded-full border transition-all ${
              niche === n.id
                ? 'bg-purple-600/30 text-purple-200 border-purple-500/40'
                : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
            }`}
          >
            {n.icon} {n.label}
          </button>
        ))}
      </div>

      {/* Mobile: carrossel snap; Desktop: grid */}
      <div className="flex md:grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-x-auto md:overflow-visible snap-x snap-mandatory px-4 md:px-0 [&>*]:w-[80vw] md:[&>*]:w-auto">
        {videos.map((item, i) => (
          <ShowcaseCard key={item.id} item={item} featured={i === 0 && niche === 'all'} />
        ))}
      </div>

      {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === 'true' && (
        <div className="text-center mt-16">
          <Link
            href="/auth/register"
            className="inline-block px-8 py-4 rounded-xl bg-purple-600/20 text-purple-300 font-semibold hover:bg-purple-600/30 border border-purple-500/30 transition-all"
          >
            Criar meu primeiro vídeo
          </Link>
        </div>
      )}
    </CinematicSection>
  )
}
