'use client'

import { useState } from 'react'
import type { CreditPackage, PaymentProvider } from '@/lib/payments'
import { createCheckout } from '@/lib/payments'
import { useToast } from '@/components/ui/feedback'

interface CreditPackageCardProps {
  pkg: CreditPackage
  highlight?: boolean
  badge?: string
  provider?: PaymentProvider
}

export default function CreditPackageCard({ pkg, highlight, badge, provider = 'stripe' }: CreditPackageCardProps) {
  const [loading, setLoading] = useState(false)
  const { error: toastError } = useToast()

  const pricePerCredit = (pkg.price_brl / 100 / pkg.credits).toFixed(2).replace('.', ',')

  async function handleBuy() {
    setLoading(true)
    try {
      const url = await createCheckout(pkg.id, provider)
      window.location.href = url
    } catch (err) {
      toastError(
        'Falha ao iniciar checkout',
        err instanceof Error ? err.message : 'Tente novamente em instantes.',
      )
      setLoading(false)
    }
  }

  return (
    <div
      className="relative flex flex-col items-center p-6 rounded-2xl transition-all duration-200"
      style={{
        background: 'var(--bg-surface)',
        border: highlight ? '2px solid var(--accent-primary, #ff5638)' : '1px solid var(--border-subtle)',
      }}
    >
      {badge && (
        <span
          className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-semibold"
          style={{
            background: 'linear-gradient(135deg, #ff5638, #6366f1)',
            color: '#fff',
          }}
        >
          {badge}
        </span>
      )}

      <h3 className="text-lg font-semibold mt-2" style={{ color: 'var(--text-primary)' }}>
        {pkg.name}
      </h3>

      <div className="mt-4 text-center">
        <span className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>
          {pkg.price_display}
        </span>
      </div>

      <div className="mt-2 text-center">
        <span className="text-2xl font-bold" style={{ color: 'var(--accent-primary, #ff5638)' }}>
          {pkg.credits}
        </span>
        <span className="text-sm ml-1" style={{ color: 'var(--text-secondary)' }}>créditos</span>
      </div>

      <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        R$ {pricePerCredit} por crédito
      </p>

      <button
        onClick={handleBuy}
        disabled={loading}
        className="mt-6 w-full py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 cursor-pointer disabled:opacity-50"
        style={{
          background: highlight
            ? 'linear-gradient(135deg, #ff5638, #6366f1)'
            : 'var(--bg-raised)',
          color: '#fff',
          border: highlight ? 'none' : '1px solid var(--border-subtle)',
        }}
      >
        {loading ? 'Redirecionando...' : 'Comprar'}
      </button>
    </div>
  )
}
