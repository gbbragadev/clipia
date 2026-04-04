'use client'

import ScrollProgress from './ScrollProgress'

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg bg-[#06060b]/70 border-b border-gray-800/50">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2 text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            <span className="inline-block w-0 h-0 border-t-[8px] border-t-transparent border-b-[8px] border-b-transparent border-l-[14px] border-l-purple-400" />
            Auto Shorts
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
