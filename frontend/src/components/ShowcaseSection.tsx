'use client'

import { useRef, useCallback, useEffect } from 'react'
import ShowcasePretextOverlay from '@/components/ShowcasePretextOverlay'
import { CinematicSection } from './ui/CinematicSection'
import { GlowCard } from './ui/GlowCard'
import { PretextHeading } from './ui/PretextHeading'
import Link from 'next/link'

const SHOWCASE_ITEMS = [
  {
    title: '5 curiosidades sobre o oceano profundo',
    template: 'Narração + Stock',
    gradient: 'from-blue-900/60 to-cyan-900/60',
    icon: '🌊',
    video: '/showcase/ocean-curiosidades.mp4',
    phrase: 'O oceano cobre mais de 70% da superficie da Terra',
    captionStyle: 'tiktok' as const,
    captionAccent: '#22d3ee',
  },
  {
    title: 'Como a IA está mudando o mundo',
    template: 'Narração + Stock',
    gradient: 'from-purple-900/60 to-indigo-900/60',
    icon: '🤖',
    video: '/showcase/ia-revolucao.mp4',
    phrase: 'Inteligencia artificial ja supera humanos em tarefas complexas',
    captionStyle: 'impact' as const,
    captionAccent: '#c084fc',
  },
  {
    title: 'Fatos surpreendentes sobre o cérebro',
    template: 'Narração + Stock',
    gradient: 'from-amber-900/60 to-orange-900/60',
    icon: '🧠',
    video: '/showcase/cerebro-fatos.mp4',
    phrase: 'Seu cerebro processa 60 mil pensamentos por dia',
    captionStyle: 'karaoke' as const,
    captionAccent: '#fb923c',
  },
]

function ShowcaseCard({ item, featured = false }: { item: (typeof SHOWCASE_ITEMS)[number], featured?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const card = cardRef.current
    const video = videoRef.current
    if (!card || !video) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          video.play().catch(() => {})
        }
      },
      { threshold: 0.3 },
    )
    observer.observe(card)
    return () => observer.disconnect()
  }, [])

  const handleEnter = useCallback(() => {
    const v = videoRef.current
    if (v) {
      v.muted = false
      v.volume = 0.6
      v.play().catch(() => {})
    }
  }, [])

  const handleLeave = useCallback(() => {
    const v = videoRef.current
    if (v) {
      v.muted = true
    }
  }, [])

  return (
    <GlowCard className={`h-full ${featured ? 'md:col-span-2' : ''}`}>
      <div
        ref={cardRef}
        className="w-full h-full relative cursor-pointer"
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onTouchStart={handleEnter}
        onTouchEnd={handleLeave}
      >
        <div className="relative w-full h-full aspect-[9/16] md:aspect-auto md:min-h-[500px] overflow-hidden">
          {item.video ? (
            <video
              ref={videoRef}
              autoPlay
              muted
              loop
              playsInline
              preload="auto"
              className="w-full h-full object-cover"
              src={item.video}
            />
          ) : (
            <div className={`w-full h-full bg-gradient-to-br ${item.gradient} flex flex-col items-center justify-center relative`}>
              <span className="text-6xl opacity-30 group-hover:opacity-50 transition">{item.icon}</span>
              <ShowcasePretextOverlay phrase={item.phrase} style={item.captionStyle} accent={item.captionAccent} />
            </div>
          )}

          {item.video && (
            <div className="absolute top-4 right-4 z-10 opacity-0 group-hover:opacity-100 transition">
              <div className="w-10 h-10 rounded-full bg-black/50 backdrop-blur-md flex items-center justify-center border border-white/10">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                  <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" />
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
            </div>
          )}

          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#0f0b1a] via-[#0f0b1a]/80 to-transparent p-6 pt-24">
            <h3 className={`font-bold text-white leading-tight ${featured ? 'text-2xl' : 'text-lg'}`}>{item.title}</h3>
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
  return (
    <CinematicSection background="none" spacing="xl" reveal="fade-up" className="border-b border-white/5">
      <div className="text-center mb-16 max-w-3xl mx-auto">
        <PretextHeading text="O que a IA cria em 2 minutos" animation="blur-focus" color="#ffffff" className="mb-6" />
        <p className="text-xl text-slate-400">
          Você digita a ideia. A IA escreve, narra e edita com legendas dinâmicas.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
        {SHOWCASE_ITEMS.map((item, i) => (
          <ShowcaseCard key={item.title} item={item} featured={i === 0} />
        ))}
      </div>

      {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === "true" && (
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
