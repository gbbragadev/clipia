'use client'

import { useRef, useCallback, useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { CinematicSection } from './ui/CinematicSection'
import { GlowCard } from './ui/GlowCard'
import { PretextHeading } from './ui/PretextHeading'
import { SkeletonBlock } from './ui/skeletons'
import Link from 'next/link'
import { loadShowcase, type ShowcaseManifest, type ShowcaseVideo } from '@/lib/showcase'
import { fadeUp, staggerContainer, useReducedMotionState } from '@/lib/motion'
import {
  isAnalyticsExampleId,
  isAnalyticsNiche,
  trackProductEvent,
} from '@/lib/analytics'

export function ShowcaseCard({
  item,
  featured = false,
  placement = 'examples',
}: {
  item: ShowcaseVideo
  featured?: boolean
  placement?: 'landing' | 'examples' | 'niche'
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const interactedRef = useRef(false)
  const completionBucketsRef = useRef(new Set<number>())

  useEffect(() => {
    const card = cardRef.current
    const video = videoRef.current
    if (!card || !video) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) video.play().catch(() => {})
        else video.pause() // pausa fora da viewport — poupa CPU/dados no mobile
      },
      { threshold: 0.3 },
    )
    observer.observe(card)
    return () => observer.disconnect()
  }, [])

  const trackInteraction = useCallback(() => {
    if (interactedRef.current || !isAnalyticsExampleId(item.id) || !isAnalyticsNiche(item.niche)) return
    interactedRef.current = true
    trackProductEvent(
      'example_played',
      { example_id: item.id, niche: item.niche, placement },
      { once: `example-played:${item.id}:${placement}` },
    )
  }, [item.id, item.niche, placement])

  const handleEnter = useCallback(() => {
    trackInteraction()
    const v = videoRef.current
    if (v) { v.muted = false; v.volume = 0.6; v.play().catch(() => {}) }
  }, [trackInteraction])
  const handleLeave = useCallback(() => { const v = videoRef.current; if (v) v.muted = true }, [])

  const handleProgress = useCallback(() => {
    const video = videoRef.current
    if (!interactedRef.current || !video || !video.duration || !isAnalyticsExampleId(item.id)) return
    const percent = (video.currentTime / video.duration) * 100
    for (const bucket of [25, 50, 75, 100] as const) {
      if (percent < bucket - (bucket === 100 ? 1 : 0) || completionBucketsRef.current.has(bucket)) continue
      completionBucketsRef.current.add(bucket)
      trackProductEvent(
        'example_completed',
        { example_id: item.id, completion_bucket: bucket },
        { once: `example-completed:${item.id}:${bucket}` },
      )
    }
  }, [item.id])

  return (
    <GlowCard className="h-full">
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
            autoPlay muted loop playsInline preload="none"
            poster={item.poster}
            className="w-full h-full object-cover"
            src={item.video}
            onTimeUpdate={handleProgress}
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
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#0b0d15] via-[#0b0d15]/80 to-transparent p-6 pt-24">
            <h3 className={`font-bold text-white leading-tight ${featured ? 'text-2xl' : 'text-lg'}`}>{item.title}</h3>
            {item.beforeScript && (
              <p className="mt-2 text-xs text-white/50 italic">Prompt: &ldquo;{item.beforeScript}&rdquo;</p>
            )}
            <div className="mt-3 flex items-center justify-between gap-2">
              <span className="inline-block text-xs px-3 py-1 rounded-full bg-white/10 text-white/80 backdrop-blur-md border border-white/5">
                {item.template}
              </span>
              {/* Link explícito (não envolve o card: hover/touch controlam o som) */}
              <Link
                href={`/v/${item.id}`}
                onClick={(e) => e.stopPropagation()}
                className="text-xs text-coral-soft hover:text-coral transition whitespace-nowrap"
              >
                Ver e compartilhar →
              </Link>
            </div>
          </div>
        </div>
      </div>
    </GlowCard>
  )
}

function ShowcaseSkeleton() {
  return (
    <div className="max-w-6xl mx-auto px-4 md:px-0">
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <SkeletonBlock key={i} className="aspect-[9/16] md:aspect-auto md:min-h-[500px] w-full" />
        ))}
      </div>
    </div>
  )
}

export default function ShowcaseSection() {
  const [manifest, setManifest] = useState<ShowcaseManifest | null>(null)
  const [niche, setNiche] = useState<string>('all')
  const reduceMotion = useReducedMotionState()

  useEffect(() => { loadShowcase().then(setManifest).catch(() => {}) }, [])

  if (!manifest) {
    return (
      <CinematicSection background="none" spacing="xl" reveal="none" className="border-b border-white/5">
        <ShowcaseSkeleton />
      </CinematicSection>
    )
  }
  const videos = niche === 'all' ? manifest.videos : manifest.videos.filter((v) => v.niche === niche)

  return (
    <CinematicSection background="none" spacing="xl" reveal="fade-up" className="border-b border-white/5">
      <div className="text-center mb-10 max-w-3xl mx-auto">
        <PretextHeading text="O que a IA cria em minutos" animation="blur-focus" color="#ffffff" className="mb-6" />
        <p className="text-xl text-slate-400">
          Vídeos reais gerados e editados no ClipIA. Passe o mouse ou toque para ouvir.
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
                ? 'bg-coral/30 text-coral-soft border-coral/40'
                : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
            }`}
          >
            {n.icon} {n.label}
          </button>
        ))}
      </div>

      {/* Mobile: carrossel snap; Desktop: grid — stagger na entrada */}
      <motion.div
        className="flex md:grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-x-auto md:overflow-visible snap-x snap-mandatory px-4 md:px-0 [&>*]:w-[80vw] md:[&>*]:w-auto [&>*]:shrink-0 md:[&>*]:shrink overscroll-x-contain scroll-px-4"
        variants={staggerContainer(0.06)}
        initial={reduceMotion ? false : 'hidden'}
        whileInView="visible"
        viewport={{ once: true, amount: 0.1 }}
      >
        {videos.map((item, i) => {
          const featured = i === 0 && niche === 'all'
          return (
            <motion.div key={item.id} variants={fadeUp} className={featured ? 'md:col-span-2' : ''}>
              <ShowcaseCard item={item} featured={featured} placement="examples" />
            </motion.div>
          )
        })}
      </motion.div>

      {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === 'true' && (
        <div className="text-center mt-16">
          <Link
            href="/auth/register"
            className="inline-block px-8 py-4 rounded-xl bg-coral/20 text-coral-soft font-semibold hover:bg-coral/30 border border-coral/30 transition-all"
          >
            Criar meu primeiro vídeo
          </Link>
        </div>
      )}
    </CinematicSection>
  )
}
