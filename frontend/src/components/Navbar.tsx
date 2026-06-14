'use client'

import Link from 'next/link'
import { strings } from '@/lib/strings';
import ScrollProgress from './ScrollProgress'
import Logo from './brand/Logo'
import ThemeToggle from './ThemeToggle'
import { useAuth } from '@/contexts/AuthContext'

export default function Navbar() {
  const { user, logout } = useAuth()

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg border-b" style={{ background: 'var(--bg-nav)', borderColor: 'var(--border-subtle)' }}>
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/">
            <Logo size="md" />
          </a>
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
        </div>
      </div>
      <ScrollProgress />
    </nav>
  )
}
