'use client'

import ScrollProgress from './ScrollProgress'

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg bg-[#06060b]/70 border-b border-gray-800/50">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2 text-xl font-bold">
            <svg width="24" height="24" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="nav-brand" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#7c3aed"/>
                  <stop offset="100%" stopColor="#3b82f6"/>
                </linearGradient>
              </defs>
              <rect x="2" y="2" width="28" height="28" rx="6" fill="none" stroke="url(#nav-brand)" strokeWidth="2.5"/>
              <polygon points="12,8 12,24 24,16" fill="url(#nav-brand)"/>
            </svg>
            <span>Clip<span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">IA</span></span>
          </a>
          <div className="hidden md:flex items-center gap-6 text-sm text-gray-400">
            <a href="#demo" className="hover:text-white transition">Demo</a>
            <a href="#como-funciona" className="hover:text-white transition">Como funciona</a>
            <a href="#waitlist" className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:opacity-90 transition">
              Acesso antecipado
            </a>
          </div>
        </div>
      </div>
      <ScrollProgress />
    </nav>
  )
}
