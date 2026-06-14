'use client'

import Link from 'next/link'
import { useState } from 'react'
import { strings } from '@/lib/strings';
import ScrollProgress from './ScrollProgress'
import Logo from './brand/Logo'
import ThemeToggle from './ThemeToggle'
import { useAuth } from '@/contexts/AuthContext'

export default function Navbar() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg border-b" style={{ background: 'var(--bg-nav)', borderColor: 'var(--border-subtle)' }}>
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" onClick={() => setOpen(false)}>
            <Logo size="md" />
          </a>

          {/* Desktop menu */}
          <div className="hidden md:flex items-center gap-5 text-sm" style={{ color: 'var(--text-secondary)' }}>
            <Link href="/exemplos" className="hover:opacity-80 transition" style={{ color: 'var(--text-secondary)' }}>Exemplos</Link>
            <Link href="/#como-funciona" className="hover:opacity-80 transition" style={{ color: 'var(--text-secondary)' }}>Como funciona</Link>
            <ThemeToggle />
            {user ? (
              <div className="flex items-center gap-3">
                {/* Avatar + credits */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
                  <span className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-[10px] font-semibold">
                    {user.name?.charAt(0).toUpperCase() || '?'}
                  </span>
                  <span className="text-purple-400 font-semibold text-xs">{user.credits}</span>
                  <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>créditos</span>
                </div>
                {/* Dashboard button */}
                <a
                  href="/dashboard"
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition"
                >
                  Dashboard
                </a>
              </div>
            ) : (
              <a href="/auth/login" className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:opacity-90 transition">
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
              className="flex h-11 w-11 items-center justify-center rounded-lg"
              style={{ color: 'var(--text-secondary)' }}
            >
              <span className="relative block h-4 w-5">
                <span className="absolute left-0 block h-0.5 w-5 bg-current transition-all" style={{ top: open ? 7 : 0, transform: open ? 'rotate(45deg)' : 'none' }} />
                <span className="absolute left-0 top-[7px] block h-0.5 w-5 bg-current transition-all" style={{ opacity: open ? 0 : 1 }} />
                <span className="absolute left-0 block h-0.5 w-5 bg-current transition-all" style={{ top: open ? 7 : 14, transform: open ? 'rotate(-45deg)' : 'none' }} />
              </span>
            </button>
          </div>
        </div>

        {/* Mobile dropdown panel */}
        {open && (
          <div className="md:hidden border-t px-4 py-4 flex flex-col gap-3 text-sm" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-nav)' }}>
            <Link href="/exemplos" onClick={() => setOpen(false)} className="py-2" style={{ color: 'var(--text-secondary)' }}>Exemplos</Link>
            <Link href="/#como-funciona" onClick={() => setOpen(false)} className="py-2" style={{ color: 'var(--text-secondary)' }}>Como funciona</Link>
            {user ? (
              <>
                <div className="flex items-center gap-2 py-1">
                  <span className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-xs font-semibold">
                    {user.name?.charAt(0).toUpperCase() || '?'}
                  </span>
                  <span className="text-purple-400 font-semibold text-sm">{user.credits}</span>
                  <span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>créditos</span>
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
          </div>
        )}
      </div>
      <ScrollProgress />
    </nav>
  )
}
