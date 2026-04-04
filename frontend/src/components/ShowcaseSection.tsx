'use client'

import { useRef, useCallback } from 'react'
import ShowcasePretextOverlay from '@/components/ShowcasePretextOverlay'

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
    title: 'Fatos que ninguém te contou sobre o cérebro',
    template: 'Gameplay Split',
    gradient: 'from-amber-900/60 to-orange-900/60',
    icon: '🧠',
    video: '/showcase/cerebro-fatos.mp4',
    phrase: 'Seu cerebro processa 60 mil pensamentos por dia',
    captionStyle: 'karaoke' as const,
    captionAccent: '#fb923c',
  },
]

function ShowcaseCard({ item }: { item: (typeof SHOWCASE_ITEMS)[number] }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  const handleEnter = useCallback(() => {
    const v = videoRef.current
    if (v) {
      v.muted = false
      v.volume = 0.6
    }
  }, [])

  const handleLeave = useCallback(() => {
    const v = videoRef.current
    if (v) {
      v.muted = true
    }
  }, [])

  return (
    <div
      className="rounded-2xl overflow-hidden border group transition cursor-pointer"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onTouchStart={handleEnter}
      onTouchEnd={handleLeave}
    >
      <div className="relative aspect-[9/16] overflow-hidden">
        {item.video ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            loop
            playsInline
            className="w-full h-full object-cover"
            src={item.video}
          />
        ) : (
          <div className={`w-full h-full bg-gradient-to-br ${item.gradient} flex flex-col items-center justify-center relative`}>
            <span className="text-6xl opacity-30 group-hover:opacity-50 transition">{item.icon}</span>
            <span className="text-xs text-gray-500 mt-4 opacity-0 group-hover:opacity-100 transition">
              Em breve
            </span>
            <ShowcasePretextOverlay phrase={item.phrase} style={item.captionStyle} accent={item.captionAccent} />
          </div>
        )}

        {/* Hover audio hint */}
        {item.video && (
          <div className="absolute top-3 right-3 z-10 opacity-0 group-hover:opacity-100 transition">
            <div className="w-7 h-7 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="white">
                <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" />
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
          </div>
        )}

        {/* Bottom overlay */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
          <p className="text-sm font-medium text-white leading-snug">{item.title}</p>
          <span className="inline-block mt-1.5 text-[10px] px-2 py-0.5 rounded-full bg-purple-500/30 text-purple-300">
            {item.template}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function ShowcaseSection() {
  return (
    <section id="showcase" className="py-24 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold">
            Vídeos criados com{' '}
            <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              ClipIA
            </span>
          </h2>
          <p className="text-gray-400 mt-3 text-sm md:text-base">
            Veja o que a plataforma consegue criar automaticamente
          </p>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {SHOWCASE_ITEMS.map((item) => (
            <ShowcaseCard key={item.title} item={item} />
          ))}
        </div>

        {/* CTA */}
        <div className="text-center mt-10">
          <a
            href="/auth/register"
            className="inline-block px-8 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold hover:opacity-90 transition"
          >
            Criar meu primeiro vídeo
          </a>
        </div>
      </div>
    </section>
  )
}
