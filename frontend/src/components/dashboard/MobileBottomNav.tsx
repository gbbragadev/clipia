'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, CreditCard, Settings, Shield } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

interface NavItem {
  href: string
  label: string
  Icon: typeof Home
  /** Match exato (true) ou startsWith (false, default). */
  exact?: boolean
  /** Escondido em certos planos (ex: só admin). */
  adminOnly?: boolean
}

const ITEMS: NavItem[] = [
  { href: '/dashboard', label: 'Início', Icon: Home, exact: true },
  { href: '/dashboard/credits', label: 'Créditos', Icon: CreditCard },
  { href: '/dashboard/settings', label: 'Config', Icon: Settings },
  { href: '/dashboard/admin', label: 'Admin', Icon: Shield, adminOnly: true },
]

/**
 * Bottom navigation fixa para mobile (<=768px).
 *some em md: para não duplicar a top navbar no desktop.
 *
 * O item ativo é determinado por usePathname() — Dashboard é match exato para
 * não marcar todas as sub-rotas; as demais usam startsWith.
 */
export function MobileBottomNav() {
  const pathname = usePathname()
  const { user } = useAuth()
  const isAdmin = user?.plan === 'admin'

  const items = ITEMS.filter((item) => !item.adminOnly || isAdmin)

  const isActive = (item: NavItem): boolean => {
    if (item.exact) return pathname === item.href
    return pathname === item.href || pathname.startsWith(item.href + '/')
  }

  return (
    <nav
      aria-label="Navegação principal"
      className="fixed bottom-0 left-0 right-0 z-40 md:hidden"
      style={{
        // safe-area: respeita o "home indicator" do iOS e barras de sistema Android.
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        background: 'var(--bg-nav, var(--bg-surface))',
        borderTop: '1px solid var(--border-subtle)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
      }}
    >
      <ul className="flex items-stretch justify-around" style={{ height: 'calc(3.5rem + env(safe-area-inset-bottom, 0px))' }}>
        {items.map((item) => {
          const { href, label, Icon } = item
          const active = isActive(item)
          return (
            <li key={href} className="flex-1">
              <Link
                href={href}
                aria-current={active ? 'page' : undefined}
                aria-label={label}
                className="flex flex-col items-center justify-center gap-0.5 h-full w-full transition-colors"
                style={{
                  color: active ? 'var(--color-coral)' : 'var(--text-tertiary)',
                  // Feedback tátil sutil no ativo
                  paddingTop: '2px',
                }}
              >
                {/* Ponto indicador do item ativo (padrão mobile-app coral) */}
                <span style={{ position: 'relative' }}>
                  <Icon className="w-5 h-5" strokeWidth={active ? 2.5 : 2} />
                  {active && (
                    <span
                      style={{
                        position: 'absolute',
                        bottom: -2,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 4,
                        height: 4,
                        borderRadius: '50%',
                        background: 'var(--color-coral)',
                      }}
                    />
                  )}
                </span>
                <span style={{
                  fontSize: 10,
                  fontWeight: active ? 600 : 500,
                  letterSpacing: 0.01,
                }}>
                  {label}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
