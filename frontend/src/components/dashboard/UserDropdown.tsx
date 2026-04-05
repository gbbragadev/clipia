'use client'

import { useState, useEffect, useRef } from 'react'
import ThemeToggle from '@/components/ThemeToggle'

interface UserDropdownProps {
  name: string
  plan?: string
  onLogout: () => void
}

export default function UserDropdown({ name, plan, onLogout }: UserDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  const initial = name?.charAt(0).toUpperCase() || '?'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-sm font-semibold hover:opacity-90 transition cursor-pointer"
      >
        {initial}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-52 rounded-xl backdrop-blur-lg shadow-xl py-1 z-50" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="px-4 py-2.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{name}</p>
            {plan && (
              <span
                className="inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase"
                style={{
                  background: plan === 'free' ? 'rgba(148,163,184,0.15)' : 'rgba(168,85,247,0.15)',
                  color: plan === 'free' ? '#94a3b8' : '#c084fc',
                }}
              >
                {plan}
              </span>
            )}
          </div>
          <a
            href="/dashboard"
            className="block px-4 py-2 text-sm transition hover:opacity-80"
            style={{ color: 'var(--text-secondary)' }}
          >
            Dashboard
          </a>
          <a
            href="/dashboard/credits"
            className="block px-4 py-2 text-sm transition hover:opacity-80"
            style={{ color: 'var(--text-secondary)' }}
          >
            Meus Créditos
          </a>
          <a
            href="/dashboard/settings"
            className="block px-4 py-2 text-sm transition hover:opacity-80"
            style={{ color: 'var(--text-secondary)' }}
          >
            Configurações
          </a>
          <div className="flex items-center justify-between px-4 py-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Tema</span>
            <ThemeToggle />
          </div>
          <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <button
              onClick={() => { setOpen(false); onLogout() }}
              className="w-full text-left px-4 py-2 text-sm hover:text-red-400 transition cursor-pointer"
              style={{ color: 'var(--text-tertiary)' }}
            >
              Sair
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
