'use client'

import { CinematicSection } from './ui/CinematicSection'
import { PretextHeading } from './ui/PretextHeading'
import { GlowCard } from './ui/GlowCard'

const steps = [
  {
    number: '01',
    title: 'Escolha um tema',
    description: 'Digite qualquer assunto e a IA gera um roteiro envolvente em pt-BR.',
    gradient: 'from-purple-900/60 to-blue-900/60',
    icon: 'edit',
  },
  {
    number: '02',
    title: 'A IA cria tudo',
    description: 'Narração com voz natural, legendas sincronizadas e mídia selecionada automaticamente.',
    gradient: 'from-fuchsia-900/60 to-purple-900/60',
    icon: 'play',
  },
  {
    number: '03',
    title: 'Edite e publique',
    description: 'Baixe em 9:16 e publique direto no YouTube Shorts, Reels ou TikTok.',
    gradient: 'from-cyan-900/60 to-blue-900/60',
    icon: 'upload',
  },
]

function StepIcon({ type }: { type: string }) {
  const size = 28
  if (type === 'edit') {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
    )
  }
  if (type === 'play') {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="5 3 19 12 5 21 5 3" fill="rgba(255,255,255,0.8)" />
      </svg>
    )
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

export default function HowItWorks() {
  return (
    <CinematicSection background="grain" spacing="xl" reveal="fade-up" className="border-b border-white/5 relative">
      <div className="absolute top-0 bottom-0 left-1/2 w-px bg-gradient-to-b from-transparent via-purple-500/20 to-transparent hidden lg:block -translate-x-1/2 z-0" />
      
      <div className="max-w-4xl mx-auto relative z-10">
        <div className="text-center mb-20">
          <p className="text-purple-400 font-medium tracking-[0.2em] uppercase text-xs mb-4">Pipeline Automático</p>
          <PretextHeading text="Do tema ao vídeo pronto" animation="typewriter" color="#ffffff" className="mb-6" />
        </div>

        <div className="space-y-12 sm:space-y-16 md:space-y-24">
          {steps.map((step, i) => {
            const isEven = i % 2 !== 0
            return (
              <div key={step.number} className={`flex flex-col lg:flex-row items-center gap-6 sm:gap-8 lg:gap-12 ${isEven ? 'lg:flex-row-reverse' : ''}`}>
                <div className={`flex-1 w-full text-center lg:text-left ${isEven ? 'lg:text-right' : ''}`}>
                  <span className="text-4xl sm:text-5xl md:text-6xl lg:text-8xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white/10 to-transparent block mb-4">
                    {step.number}
                  </span>
                  <h3 className="text-2xl md:text-3xl font-bold text-white mb-4">{step.title}</h3>
                  <p className={`text-lg text-slate-400 leading-relaxed max-w-md mx-auto lg:mx-0 ${isEven ? 'lg:ml-auto lg:mr-0' : ''}`}>
                    {step.description}
                  </p>
                </div>
                
                <div className="flex-1 w-full max-w-sm">
                  <GlowCard intensity={0.4}>
                    <div className={`aspect-square w-full bg-gradient-to-br ${step.gradient} rounded-2xl flex items-center justify-center relative overflow-hidden p-8`}>
                      <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 mix-blend-overlay" />
                      <div className="w-24 h-24 rounded-full bg-black/40 backdrop-blur-xl border border-white/10 flex items-center justify-center shadow-2xl relative z-10 transform hover:scale-110 transition duration-500">
                        <StepIcon type={step.icon} />
                      </div>
                    </div>
                  </GlowCard>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </CinematicSection>
  )
}
