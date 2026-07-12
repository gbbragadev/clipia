'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, animate } from 'motion/react'
import { LayoutDashboard, LogIn } from 'lucide-react'
import { strings } from '@/lib/strings'
import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'
import ScrollProgress from './ScrollProgress'
import Logo from './brand/Logo'
import { useAuth } from '@/contexts/AuthContext'

/** Número de créditos com tick animado: conta do valor antigo pro novo e dá um
 *  pop sutil quando muda. Reduced-motion: troca direta. */
function CreditsValue({ value, className }: { value: number; className: string }) {
  const reduceMotion = useReducedMotionState()
  const ref = useRef<HTMLSpanElement>(null)
  const prevRef = useRef(value)
  useEffect(() => {
    const prev = prevRef.current
    prevRef.current = value
    const el = ref.current
    if (!el || prev === value) return
    if (reduceMotion) {
      el.textContent = String(value)
      return
    }
    const controls = animate(prev, value, {
      duration: 0.6,
      ease: EASE,
      onUpdate: (v) => { el.textContent = String(Math.round(v)) },
    })
    const pop = animate(el, { scale: [1, 1.06, 1] }, { duration: 0.35, ease: EASE })
    return () => { controls.stop(); pop.stop() }
  }, [value, reduceMotion])
  return <span ref={ref} className={`inline-block ${className}`}>{value}</span>
}

export default function Navbar() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const reduceMotion = useReducedMotionState()

  // Scroll-aware: reforça o glass quando sai do topo.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // ESC fecha o menu mobile.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const panelTransition = { duration: DURATIONS.normal, ease: EASE }

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div
        className={`backdrop-blur-lg border-b transition-shadow duration-300 ${scrolled ? 'shadow-lg shadow-black/20' : ''}`}
        style={{ background: 'var(--bg-nav)', borderColor: 'var(--border-subtle)' }}
      >
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" onClick={() => setOpen(false)}>
            <Logo size="md" />
          </a>

          {/* Desktop menu */}
          <div className="hidden md:flex items-center gap-5 text-sm text-2">
            <Link href="/exemplos" className="hover:opacity-80 transition">Exemplos</Link>
            <Link href="/#como-funciona" className="hover:opacity-80 transition">Como funciona</Link>
            {user ? (
              <div className="flex items-center gap-3">
                {/* Avatar + credits */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface" style={{ border: '1px solid var(--border-subtle)' }}>
                  <span className="w-6 h-6 rounded-full bg-gradient-to-br from-coral to-azure flex items-center justify-center text-white text-[10px] font-semibold">
                    {user.name?.charAt(0).toUpperCase() || '?'}
                  </span>
                  <CreditsValue value={user.credits} className="text-coral font-semibold text-xs" />
                  <span className="text-xs text-3">créditos</span>
                </div>
                {/* Dashboard button */}
                <a
                  href="/dashboard"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-coral to-azure text-white text-sm font-medium hover:opacity-90 active:scale-[0.97] transition"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </a>
              </div>
            ) : (
              <a href="/auth/login" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-coral to-azure text-white hover:opacity-90 active:scale-[0.97] transition">
                <LogIn className="w-4 h-4" />
                {strings.auth.login.submit}
              </a>
            )}
          </div>

          {/* Mobile: hamburger */}
          <div className="flex items-center gap-2 md:hidden">
            <button
              type="button"
              aria-label={open ? 'Fechar menu' : 'Abrir menu'}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              className="flex h-11 w-11 items-center justify-center rounded-lg text-2"
            >
              <span className="relative block h-4 w-5">
                <span className="absolute left-0 top-0 block h-0.5 w-5 bg-current transition-transform duration-200" style={{ transform: open ? 'translateY(7px) rotate(45deg)' : 'none' }} />
                <span className="absolute left-0 top-[7px] block h-0.5 w-5 bg-current transition-opacity duration-200" style={{ opacity: open ? 0 : 1 }} />
                <span className="absolute left-0 top-[14px] block h-0.5 w-5 bg-current transition-transform duration-200" style={{ transform: open ? 'translateY(-7px) rotate(-45deg)' : 'none' }} />
              </span>
            </button>
          </div>
        </div>

        {/* Mobile dropdown panel — animado (height + opacity) */}
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              className="md:hidden overflow-hidden border-t px-4 flex flex-col gap-1 text-sm"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-nav)' }}
              initial={reduceMotion ? false : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
              transition={panelTransition}
            >
              <Link href="/exemplos" onClick={() => setOpen(false)} className="py-3 text-2">Exemplos</Link>
              <Link href="/#como-funciona" onClick={() => setOpen(false)} className="py-3 text-2">Como funciona</Link>
              {user ? (
                <>
                  <div className="flex items-center gap-2 py-3">
                    <span className="w-7 h-7 rounded-full bg-gradient-to-br from-coral to-azure flex items-center justify-center text-white text-xs font-semibold">
                      {user.name?.charAt(0).toUpperCase() || '?'}
                    </span>
                    <CreditsValue value={user.credits} className="text-coral font-semibold text-sm" />
                    <span className="text-sm text-3">créditos</span>
                  </div>
                  <a href="/dashboard" onClick={() => setOpen(false)} className="w-full text-center px-4 py-3 rounded-lg bg-gradient-to-r from-coral to-azure text-white font-medium active:scale-[0.97] transition">
                    Dashboard
                  </a>
                </>
              ) : (
                <a href="/auth/login" onClick={() => setOpen(false)} className="w-full text-center px-4 py-3 rounded-lg bg-gradient-to-r from-coral to-azure text-white font-medium active:scale-[0.97] transition">
                  {strings.auth.login.submit}
                </a>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Backdrop mobile — outside-click fecha o menu */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.button
            type="button"
            aria-label="Fechar menu"
            onClick={() => setOpen(false)}
            className="md:hidden fixed inset-0 top-16 z-[-1] bg-black/30 backdrop-blur-sm cursor-default"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={panelTransition}
          />
        )}
      </AnimatePresence>

      <ScrollProgress />
    </nav>
  )
}
