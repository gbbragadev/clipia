'use client'

import { useRef } from 'react'
import VideoShowcase from './VideoShowcase'
import PretextCanvas from './PretextCanvas'
import { CinematicSection } from '../ui/CinematicSection'
import { PretextHeading } from '../ui/PretextHeading'
import Link from 'next/link'

export default function HeroSection() {
  return (
    <CinematicSection background="mesh" spacing="xl" reveal="fade-up" className="min-h-screen flex flex-col justify-center border-b border-white/5">
      <div className="w-full grid lg:grid-cols-[1fr_auto] gap-12 items-center">
        {/* Left: Typography as star */}
        <div className="flex flex-col space-y-8 z-10 relative">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-300 text-sm w-max">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            Beta privado
          </div>

          <div className="w-full">
            <PretextHeading 
              text="Crie vídeos que ninguém pula" 
              animation="pop" 
              color="#ffffff" 
              className="mb-4"
            />
          </div>

          <p className="text-xl md:text-2xl text-slate-400 max-w-2xl leading-relaxed">
            Roteiro, narração, legendas animadas e edição. <br/>Tudo automático em minutos.
          </p>

          <div className="w-full max-w-2xl bg-black/40 p-4 rounded-xl border border-white/5 backdrop-blur-md">
             <PretextCanvas />
          </div>

          <div className="flex flex-col sm:flex-row gap-4 pt-4">
            <Link href="/auth/register" className="px-8 py-4 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl transition-all shadow-[0_0_30px_rgba(124,58,237,0.3)] hover:shadow-[0_0_50px_rgba(124,58,237,0.5)] text-center">
              Criar meu primeiro vídeo
            </Link>
            <Link href="#demo" className="px-8 py-4 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all text-center">
              Ver como funciona
            </Link>
          </div>
        </div>

        {/* Right: Subordinate phone mockup */}
        <div className="w-full max-w-[320px] mx-auto lg:mx-0 relative">
          <div className="absolute inset-0 bg-purple-600/20 blur-[100px] rounded-full" />
          <VideoShowcase />
        </div>
      </div>
    </CinematicSection>
  )
}
