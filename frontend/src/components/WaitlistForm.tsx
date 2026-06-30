'use client'

import { motion } from 'motion/react'
import { Sparkles, Check } from 'lucide-react'
import Link from 'next/link'
import { SPRING } from '@/lib/motion'

const MotionLink = motion.create(Link)

export default function WaitlistForm() {
  return (
    <section id="waitlist" className="py-24 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative border-dashed border-l-2 border-r-2 border-purple-500/30 rounded-2xl bg-[var(--bg-card)] overflow-hidden shadow-2xl shadow-purple-900/20">
          <div className="filmstrip-border w-full opacity-40" />

          <div className="absolute top-6 -left-3 w-6 h-6 rounded-full bg-[var(--background)] hidden sm:block" />
          <div className="absolute bottom-6 -left-3 w-6 h-6 rounded-full bg-[var(--background)] hidden sm:block" />
          <div className="absolute top-6 -right-3 w-6 h-6 rounded-full bg-[var(--background)] hidden sm:block" />
          <div className="absolute bottom-6 -right-3 w-6 h-6 rounded-full bg-[var(--background)] hidden sm:block" />

          <div className="p-6 sm:p-10 text-center">
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4">Comece a criar vídeos hoje</h2>
            <p className="text-gray-400 mb-8 max-w-md mx-auto text-lg">
              2 vídeos grátis para você experimentar. Sem necessidade de cartão de crédito.
            </p>

            {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === "true" && (
              <MotionLink
                href="/auth/register"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.97 }}
                transition={SPRING}
                className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold hover:opacity-90 transition text-lg shadow-lg shadow-purple-500/20"
              >
                <Sparkles className="w-5 h-5" />
                Criar minha conta grátis
              </MotionLink>
            )}

            {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === "true" && (
              <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm text-gray-500">
                <span className="inline-flex items-center gap-1.5"><Check className="w-4 h-4 text-green-400" /> 2 vídeos grátis</span>
                <span className="inline-flex items-center gap-1.5"><Check className="w-4 h-4 text-green-400" /> Sem cartão de crédito</span>
                <span className="inline-flex items-center gap-1.5"><Check className="w-4 h-4 text-green-400" /> Leva 2 minutos</span>
              </div>
            )}
          </div>

          <div className="filmstrip-border w-full opacity-40" />
        </div>
      </div>
    </section>
  )
}
