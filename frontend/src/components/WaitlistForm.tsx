'use client'

import { useState, useEffect } from 'react'

export default function WaitlistForm() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('waitlist_email')
    if (saved) setSubmitted(true)
  }, [])

  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    try {
      await fetch("/api/v1/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      setSubmitted(true)
      localStorage.setItem('waitlist_email', email)
    } catch {
      setSubmitted(true)
      localStorage.setItem('waitlist_email', email)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section id="waitlist" className="py-20 px-4">
      <div className="max-w-md mx-auto">
        {/* Ticket card */}
        <div className="relative border-dashed border-l-2 border-r-2 border-purple-500/30 rounded-2xl bg-[var(--bg-card)] overflow-hidden">
          {/* Filmstrip decoration on top */}
          <div className="filmstrip-border w-full opacity-40" />

          {/* Punch holes */}
          <div className="absolute top-6 -left-3 w-6 h-6 rounded-full bg-[var(--background)]" />
          <div className="absolute bottom-6 -left-3 w-6 h-6 rounded-full bg-[var(--background)]" />
          <div className="absolute top-6 -right-3 w-6 h-6 rounded-full bg-[var(--background)]" />
          <div className="absolute bottom-6 -right-3 w-6 h-6 rounded-full bg-[var(--background)]" />

          {/* Content */}
          <div className="p-8 text-center">
            <h2 className="text-sm font-mono text-purple-400/70 tracking-wider mb-2">
              Premiere
            </h2>
            <h3 className="text-2xl font-bold mb-2">Acesso Antecipado</h3>
            <p className="text-gray-400 mb-8">
              Seja um dos primeiros a usar o ClipIA quando lancarmos.
            </p>

            {submitted ? (
              <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400">
                Voce esta na lista! Entraremos em contato em breve.
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="seu@email.com"
                  required
                  className="flex-1 px-4 py-3 rounded-lg bg-white/5 border border-gray-700 text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none transition"
                />
                <button
                  type="submit"
                  className="px-6 py-3 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium hover:opacity-90 transition whitespace-nowrap"
                >
                  Quero acesso
                </button>
              </form>
            )}
          </div>

          {/* Filmstrip decoration on bottom */}
          <div className="filmstrip-border w-full opacity-40" />
        </div>
      </div>
    </section>
  )
}
