'use client'

import Link from 'next/link'

export default function WaitlistForm() {
  return (
    <section id="waitlist" className="py-24 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative border-dashed border-l-2 border-r-2 border-purple-500/30 rounded-2xl bg-[var(--bg-card)] overflow-hidden shadow-2xl shadow-purple-900/20">
          <div className="filmstrip-border w-full opacity-40" />

          <div className="absolute top-6 -left-3 w-6 h-6 rounded-full bg-[var(--background)]" />
          <div className="absolute bottom-6 -left-3 w-6 h-6 rounded-full bg-[var(--background)]" />
          <div className="absolute top-6 -right-3 w-6 h-6 rounded-full bg-[var(--background)]" />
          <div className="absolute bottom-6 -right-3 w-6 h-6 rounded-full bg-[var(--background)]" />

          <div className="p-10 text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Comece a criar vídeos hoje</h2>
            <p className="text-gray-400 mb-8 max-w-md mx-auto text-lg">
              2 vídeos grátis para você experimentar. Sem necessidade de cartão de crédito.
            </p>

            {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === "true" && (
              <Link
                href="/auth/register"
                className="inline-block px-8 py-4 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold hover:opacity-90 transition text-lg shadow-lg shadow-purple-500/20"
              >
                Criar minha conta grátis
              </Link>
            )}
          </div>

          <div className="filmstrip-border w-full opacity-40" />
        </div>
      </div>
    </section>
  )
}
