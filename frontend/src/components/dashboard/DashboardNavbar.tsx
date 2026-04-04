'use client'

import { useAuth } from '@/contexts/AuthContext'
import Logo from '@/components/brand/Logo'
import CreditsBadge from './CreditsBadge'
import UserDropdown from './UserDropdown'

export default function DashboardNavbar() {
  const { user, logout } = useAuth()

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg bg-[#06060b]/70 border-b border-gray-800/50">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <a href="/dashboard">
            <Logo size="sm" />
          </a>

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
