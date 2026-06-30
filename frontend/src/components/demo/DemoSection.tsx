'use client'

import { useVideoGeneration } from '@/hooks/useVideoGeneration'
import GenerateForm from './GenerateForm'
import ProgressBar from './ProgressBar'
import VideoPlayer from './VideoPlayer'
import { CinematicSection } from '../ui/CinematicSection'
import { GlowCard } from '../ui/GlowCard'
import { PretextHeading } from '../ui/PretextHeading'

export default function DemoSection() {
  const { generate, status, isGenerating, error, downloadUrl, stepLabel } = useVideoGeneration()

  return (
    <CinematicSection id="demo" background="none" spacing="xl" className="border-b border-white/5">
      <div className="grid lg:grid-cols-2 gap-12 lg:gap-24 items-center max-w-6xl mx-auto">
        <div className="order-2 lg:order-1">
          <div className="mb-8">
            <span className="inline-block py-1 px-3 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs font-semibold tracking-wider uppercase mb-4">
              Demo Interativa
            </span>
            <PretextHeading text="Experimente agora" animation="pop" color="#ffffff" className="mb-4" />
            <p className="text-xl text-slate-400 leading-relaxed">
              Digite um tema e veja a IA organizar cenas, narrar com voz neural e montar seu vídeo no formato 9:16.
            </p>
          </div>
          
          <GlowCard intensity={0.4}>
            <div className="rounded-2xl bg-[#0a0a14] border border-white/10 overflow-hidden relative">
              <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 pointer-events-none mix-blend-overlay"></div>
              
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-black/40 backdrop-blur-xl relative z-10">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500/80 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80 shadow-[0_0_10px_rgba(234,179,8,0.5)]" />
                  <div className="w-3 h-3 rounded-full bg-green-500/80 shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                </div>
                <span className="text-xs text-slate-400 font-mono tracking-wider">ClipIA Editor</span>
                <div className="w-12"></div>
              </div>

              <div className="p-6 md:p-8 relative z-10 space-y-6">
                <GenerateForm
                  onGenerate={(topic, style, duration) =>
                    generate({ topic, style, duration_target: duration })
                  }
                  isGenerating={isGenerating}
                />

                {(isGenerating || status) && !downloadUrl && !error && (
                  <div className="mt-8 border-t border-white/5 pt-6">
                    <ProgressBar
                      progress={status?.progress || 0}
                      currentStep={status?.current_step || null}
                      stepLabel={stepLabel}
                    />
                  </div>
                )}

                {error && (
                  <div className="mt-8 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-medium">
                    {error}
                  </div>
                )}

                {downloadUrl && (
                  <div className="mt-8 border-t border-white/5 pt-6">
                    <VideoPlayer downloadUrl={downloadUrl} />
                  </div>
                )}
              </div>
            </div>
          </GlowCard>
        </div>

        <div className="order-1 lg:order-2 flex flex-col gap-6">
          <div className="rounded-2xl border border-white/5 bg-[#1a1425]/50 p-8 backdrop-blur-xl relative overflow-hidden">
             <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/10 blur-[100px] rounded-full pointer-events-none"></div>
             <h4 className="text-white font-semibold mb-4 text-lg">Roteiro com gancho, cena a cena</h4>
             <p className="text-slate-400 text-sm leading-relaxed mb-6">
               A IA escreve o roteiro em pt-BR já dividido em cenas cronometradas — começando por um gancho nos primeiros segundos pra segurar o espectador.
             </p>
             <div className="grid grid-cols-2 gap-4 text-xs font-mono text-purple-300 opacity-70">
               <div className="bg-black/40 p-4 rounded-lg border border-purple-500/20">
                 [Cena 1]<br/><br/>
                 Oceano profundo...<br/>
                 (12s)
               </div>
               <div className="bg-black/40 p-4 rounded-lg border border-purple-500/20">
                 [Cena 2]<br/><br/>
                 Criaturas bioluminescentes...<br/>
                 (18s)
               </div>
             </div>
          </div>

          <div className="rounded-2xl border border-white/5 bg-[#1a1425]/50 p-8 backdrop-blur-xl relative overflow-hidden">
             <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-500/10 blur-[100px] rounded-full pointer-events-none"></div>
             <h4 className="text-white font-semibold mb-4 text-lg">Legendas no tempo exato da fala</h4>
             <p className="text-slate-400 text-sm leading-relaxed mb-6">
               Cada palavra entra sincronizada com a narração, em 5 estilos animados prontos pra TikTok, Reels e Shorts.
             </p>
             <div className="w-full h-12 bg-black/40 rounded-lg border border-white/5 flex items-center px-4 gap-1 relative overflow-hidden">
               <div className="absolute inset-0 w-full h-full" style={{ background: 'linear-gradient(90deg, rgba(124, 58, 237, 0.2) 0%, transparent 100%)', transform: 'translateX(-50%)', animation: 'slideRight 3s infinite linear' }}></div>
               <span className="text-white z-10 text-sm">Oceano</span>
               <span className="text-purple-400 z-10 text-sm">profundo</span>
               <span className="text-slate-600 z-10 text-sm opacity-50">...</span>
             </div>
          </div>
        </div>
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideRight {
          from { transform: translateX(-100%); }
          to { transform: translateX(100%); }
        }
      `}} />
    </CinematicSection>
  )
}
