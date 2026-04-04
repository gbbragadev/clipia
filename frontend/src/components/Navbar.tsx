'use client'

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
            <a href="#showcase" className="hover:opacity-80 transition" style={{ color: 'var(--text-secondary)' }}>Exemplos</a>
            <a href="#como-funciona" className="hover:opacity-80 transition" style={{ color: 'var(--text-secondary)' }}>Como funciona</a>
            <ThemeToggle />
            {user ? (
              <div className="flex items-center gap-4">
                <a href="/dashboard" className="font-medium hover:text-purple-400 transition" style={{ color: 'var(--text-primary)' }}>
                  Dashboard
                </a>
                <span style={{ color: 'var(--text-secondary)' }}>
                  <span className="text-purple-400 font-semibold">{user.credits}</span> créditos
                </span>
                <button onClick={logout} className="hover:text-red-400 transition cursor-pointer" style={{ color: 'var(--text-tertiary)' }}>
                  Sair
                </button>
              </div>
            ) : (
              <a href="/auth/login" className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:opacity-90 transition">
                Entrar
              </a>
            )}
          </div>
        </div>
      </div>
      <ScrollProgress />
    </nav>
  )
}
