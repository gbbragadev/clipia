'use client'

import { useInView } from '@/hooks/useInView'

const panels = [
  {
    timecode: '00:01',
    title: 'Escolha o tema',
    description: 'Digite qualquer assunto — de curiosidades cientificas a noticias do dia.',
  },
  {
    timecode: '00:02',
    title: 'IA gera o video',
    description: 'Roteiro, narracao em pt-BR, selecao de midia e legendas sincronizadas automaticamente.',
  },
  {
    timecode: '00:03',
    title: 'Publique',
    description: 'Baixe o video pronto em formato 9:16 e publique no YouTube Shorts, Reels ou TikTok.',
  },
]

function ThumbnailInput() {
  return (
    <div className="w-full rounded-xl bg-[#0a0a14] border border-gray-800 p-4 flex flex-col gap-2" style={{ aspectRatio: '9/16' }}>
      <div className="flex-1 flex flex-col justify-center gap-3 px-2">
        <div className="h-3 w-3/4 rounded bg-gray-700/50" />
        <div className="h-3 w-1/2 rounded bg-gray-700/50" />
        <div className="flex items-center gap-1 mt-2">
          <div className="h-4 w-full rounded bg-purple-500/20 border border-purple-500/30 flex items-center px-2">
            <span className="text-[10px] text-purple-300 font-mono">5 fatos sobre...</span>
            <span className="ml-auto w-0.5 h-3 bg-purple-400" style={{ animation: 'cursor-blink 1s infinite' }} />
          </div>
        </div>
      </div>
    </div>
  )
}

function ThumbnailTimeline() {
  return (
    <div className="w-full rounded-xl bg-[#0a0a14] border border-gray-800 p-4 flex flex-col justify-center gap-3" style={{ aspectRatio: '9/16' }}>
      <div className="space-y-3 px-2">
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-gray-600 font-mono w-6">AUD</span>
          <div className="flex-1 h-3 rounded bg-blue-500/30 border border-blue-500/20" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-gray-600 font-mono w-6">VID</span>
          <div className="flex-1 h-3 rounded bg-purple-500/30 border border-purple-500/20 animate-pulse" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-gray-600 font-mono w-6">TXT</span>
          <div className="flex-1 h-3 rounded bg-fuchsia-500/30 border border-fuchsia-500/20" />
        </div>
      </div>
      <div className="mt-2 h-px bg-gradient-to-r from-transparent via-purple-500/40 to-transparent" />
      <div className="flex justify-between text-[8px] text-gray-600 font-mono px-2">
        <span>00:00</span>
        <span>00:15</span>
        <span>00:30</span>
      </div>
    </div>
  )
}

function ThumbnailPublish() {
  return (
    <div className="w-full rounded-xl bg-[#0a0a14] border border-gray-800 p-4 flex flex-col justify-center items-center gap-4" style={{ aspectRatio: '9/16' }}>
      <div className="flex gap-4 items-center">
        {/* YouTube circle */}
        <div className="w-12 h-12 rounded-full bg-red-500/20 border-2 border-red-500/40 flex items-center justify-center">
          <div className="w-0 h-0 border-t-[6px] border-t-transparent border-b-[6px] border-b-transparent border-l-[10px] border-l-red-400 ml-1" />
        </div>
        {/* Instagram circle */}
        <div className="w-12 h-12 rounded-full bg-pink-500/20 border-2 border-pink-500/40 flex items-center justify-center">
          <div className="w-5 h-5 rounded-md border-2 border-pink-400">
            <div className="w-1.5 h-1.5 rounded-full bg-pink-400 mx-auto mt-0.5" />
          </div>
        </div>
        {/* TikTok circle */}
        <div className="w-12 h-12 rounded-full bg-cyan-500/20 border-2 border-cyan-500/40 flex items-center justify-center">
          <div className="relative">
            <div className="w-3 h-4 border-2 border-cyan-400 rounded-sm" />
            <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-cyan-400" />
          </div>
        </div>
      </div>
      <div className="h-2 w-20 rounded-full bg-green-500/30 border border-green-500/20" />
      <span className="text-[10px] text-gray-500 font-mono">Pronto para publicar</span>
    </div>
  )
}

export default function HowItWorks() {
  const { ref, inView } = useInView(0.15)

  return (
    <section id="como-funciona" className="py-20 px-4" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <h2 className="text-sm font-mono text-gray-500 text-center mb-2 tracking-wider">
          Cena 03 &middot; Storyboard
        </h2>
        <h3 className="text-2xl font-bold text-center mb-12">Como funciona</h3>

        <div className="grid md:grid-cols-[1fr_auto_1fr_auto_1fr] gap-4 md:gap-6 items-start">
          {panels.map((panel, i) => (
            <div key={panel.timecode} className="contents">
              <div
                className={`p-5 rounded-2xl bg-[var(--bg-card)] border border-gray-800 hover:border-purple-500/30 transition-all duration-700 group ${
                  inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                }`}
                style={{ transitionDelay: `${i * 200}ms` }}
              >
                <span className="text-[10px] font-mono text-gray-600 block mb-3">{panel.timecode}</span>
                <div className="mb-4">
                  {i === 0 && <ThumbnailInput />}
                  {i === 1 && <ThumbnailTimeline />}
                  {i === 2 && <ThumbnailPublish />}
                </div>
                <h4 className="text-lg font-semibold mb-2 group-hover:text-purple-300 transition">
                  {panel.title}
                </h4>
                <p className="text-gray-400 text-sm leading-relaxed">{panel.description}</p>
              </div>
              {/* Arrow connector (desktop only, not after last panel) */}
              {i < panels.length - 1 && (
                <div className="hidden md:flex items-center justify-center self-center">
                  <div className="w-0 h-0 border-t-[8px] border-t-transparent border-b-[8px] border-b-transparent border-l-[12px] border-l-purple-500/40" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
