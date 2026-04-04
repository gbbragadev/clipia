'use client'

import { useState, useEffect, useRef } from 'react'

interface UserDropdownProps {
  name: string
  onLogout: () => void
}

export default function UserDropdown({ name, onLogout }: UserDropdownProps) {
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
        <div className="absolute right-0 mt-2 w-48 rounded-xl backdrop-blur-lg shadow-xl py-1 z-50" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="px-4 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{name}</p>
          </div>
          <a
            href="/dashboard"
            className="block px-4 py-2 text-sm transition hover:opacity-80" style={{ color: 'var(--text-secondary)' }}
          >
            Dashboard
          </a>
          <div style={{ borderTop: '1px solid var(--border-subtle)' }} className="mt-1">
            <button
              onClick={() => { setOpen(false); onLogout() }}
              className="w-full text-left px-4 py-2 text-sm hover:text-red-400 transition cursor-pointer" style={{ color: 'var(--text-tertiary)' }}
            >
              Sair
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
