'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { LayoutDashboard, LogIn } from 'lucide-react'
import { strings } from '@/lib/strings'
import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'
import ScrollProgress from './ScrollProgress'
import Logo from './brand/Logo'
import ThemeToggle from './ThemeToggle'
import { useAuth } from '@/contexts/AuthContext'

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
            <ThemeToggle />
            {user ? (
              <div className="flex items-center gap-3">
                {/* Avatar + credits */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface" style={{ border: '1px solid var(--border-subtle)' }}>
                  <span className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-[10px] font-semibold">
                    {user.name?.charAt(0).toUpperCase() || '?'}
                  </span>
                  <span className="text-purple-400 font-semibold text-xs">{user.credits}</span>
                  <span className="text-xs text-3">créditos</span>
                </div>
                {/* Dashboard button */}
                <a
                  href="/dashboard"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </a>
              </div>
            ) : (
              <a href="/auth/login" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:opacity-90 transition">
                <LogIn className="w-4 h-4" />
                {strings.auth.login.submit}
              </a>
            )}
          </div>

          {/* Mobile: theme toggle + hamburger */}
          <div className="flex items-center gap-2 md:hidden">
            <ThemeToggle />
            <button
              type="button"
              aria-label={open ? 'Fechar menu' : 'Abrir menu'}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              className="flex h-11 w-11 items-center justify-center rounded-lg text-2"
            >
              <span className="relative block h-4 w-5">
                <span className="absolute left-0 block h-0.5 w-5 bg-current transition-all" style={{ top: open ? 7 : 0, transform: open ? 'rotate(45deg)' : 'none' }} />
                <span className="absolute left-0 top-[7px] block h-0.5 w-5 bg-current transition-all" style={{ opacity: open ? 0 : 1 }} />
                <span className="absolute left-0 block h-0.5 w-5 bg-current transition-all" style={{ top: open ? 7 : 14, transform: open ? 'rotate(-45deg)' : 'none' }} />
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
                    <span className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-xs font-semibold">
                      {user.name?.charAt(0).toUpperCase() || '?'}
                    </span>
                    <span className="text-purple-400 font-semibold text-sm">{user.credits}</span>
                    <span className="text-sm text-3">créditos</span>
                  </div>
                  <a href="/dashboard" onClick={() => setOpen(false)} className="w-full text-center px-4 py-3 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium">
                    Dashboard
                  </a>
                </>
              ) : (
                <a href="/auth/login" onClick={() => setOpen(false)} className="w-full text-center px-4 py-3 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium">
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
