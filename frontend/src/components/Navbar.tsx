'use client'

import ScrollProgress from './ScrollProgress'
import Logo from './brand/Logo'
import { useAuth } from '@/contexts/AuthContext'

export default function Navbar() {
  const { user, logout } = useAuth()

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg bg-[#06060b]/70 border-b border-gray-800/50">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/">
            <Logo size="md" />
          </a>
          <div className="hidden md:flex items-center gap-6 text-sm text-gray-400">
            <a href="#showcase" className="hover:text-white transition">Exemplos</a>
            <a href="#como-funciona" className="hover:text-white transition">Como funciona</a>
            {user ? (
              <div className="flex items-center gap-4">
                <a href="/dashboard" className="text-white font-medium hover:text-purple-300 transition">
                  Dashboard
                </a>
                <span className="text-slate-300">
                  <span className="text-purple-400 font-semibold">{user.credits}</span> créditos
                </span>
                <button onClick={logout} className="text-slate-400 hover:text-white transition cursor-pointer">
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
