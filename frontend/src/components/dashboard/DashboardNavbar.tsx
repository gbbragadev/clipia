'use client'

import { useAuth } from '@/contexts/AuthContext'
import Logo from '@/components/brand/Logo'
import CreditsBadge from './CreditsBadge'
import UserDropdown from './UserDropdown'

export default function DashboardNavbar() {
  const { user, logout } = useAuth()

  return (
    <nav className="fixed top-0 left-0 right-0 z-40">
      <div className="backdrop-blur-lg border-b" style={{ background: 'var(--bg-nav)', borderColor: 'var(--border-subtle)' }}>
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <a href="/">
            <Logo size="sm" />
          </a>

          {user && (
            <div className="flex items-center gap-3">
              {user.plan === 'admin' && (
                <a
                  href="/dashboard/admin"
                  className="hidden rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] md:inline-flex"
                  style={{ borderColor: 'rgba(34,197,94,0.25)', color: '#86efac', background: 'rgba(34,197,94,0.08)' }}
                >
                  Admin
                </a>
              )}
              <a href="/dashboard/credits" className="transition-opacity hover:opacity-80">
                <CreditsBadge credits={user.credits} />
              </a>
              <UserDropdown name={user.name} plan={user.plan} onLogout={logout} />
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
