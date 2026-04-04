'use client'

import { useAuth } from '@/contexts/AuthContext'
import CreditsBadge from './CreditsBadge'
import UserDropdown from './UserDropdown'

export default function DashboardNavbar() {
  const { user, logout } = useAuth()

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg bg-[#06060b]/70 border-b border-gray-800/50">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          {/* Logo */}
          <a href="/dashboard" className="flex items-center gap-2 text-lg font-bold">
            <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
              <defs>
                <linearGradient id="dash-brand" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#7c3aed" />
                  <stop offset="100%" stopColor="#3b82f6" />
                </linearGradient>
              </defs>
              <rect x="2" y="2" width="28" height="28" rx="6" fill="none" stroke="url(#dash-brand)" strokeWidth="2.5" />
              <polygon points="12,8 12,24 24,16" fill="url(#dash-brand)" />
            </svg>
            <span>
              Clip<span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">IA</span>
            </span>
          </a>

          {/* Right side */}
          {user && (
            <div className="flex items-center gap-3">
              <CreditsBadge credits={user.credits} />
              <UserDropdown name={user.name} onLogout={logout} />
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
