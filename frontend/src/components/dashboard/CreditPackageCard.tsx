'use client'

import type { CreditPackage } from '@/lib/payments'
import { apiIdToSelectedPackage, selectedPackageLabel } from '@/lib/package-intent'

interface CreditPackageCardProps {
  pkg: CreditPackage
  highlight?: boolean
  badge?: string
  selected?: boolean
  onSelect: () => void
}

export default function CreditPackageCard({ pkg, highlight, badge, selected = false, onSelect }: CreditPackageCardProps) {
  const totalCredits = pkg.credits + (pkg.bonus_credits ?? 0)
  const pricePerCredit = (pkg.price_brl / 100 / totalCredits).toFixed(2).replace('.', ',')
  const intent = apiIdToSelectedPackage(pkg.id)
  const displayName = intent ? selectedPackageLabel(intent) : pkg.name

  return (
    <div
      data-package-id={pkg.id}
      aria-current={selected ? 'true' : undefined}
      className="relative flex flex-col items-center p-6 rounded-2xl transition-all duration-200"
      style={{
        background: 'var(--bg-surface)',
        border: selected || highlight ? '2px solid var(--accent-primary, #ff5638)' : '1px solid var(--border-subtle)',
      }}
    >
      {(selected || badge) && (
        <span
          className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-semibold"
          style={{
            background: 'linear-gradient(135deg, #ff5638, #3e9bff)',
            color: '#fff',
          }}
        >
          {selected ? 'Pacote preselecionado' : badge}
        </span>
      )}

      <h3 className="text-lg font-semibold mt-2" style={{ color: 'var(--text-primary)' }}>
        {displayName}
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

      {pkg.bonus_credits > 0 && (
        <span
          className="mt-2 px-2.5 py-0.5 rounded-full text-xs font-semibold"
          style={{
            background: 'rgba(67,224,173,0.12)',
            color: '#43e0ad',
            border: '1px solid rgba(67,224,173,0.3)',
          }}
        >
          +{pkg.bonus_credits} bônus · {totalCredits} no total
        </span>
      )}

      {/* Mesma narrativa de preço da landing: custo por VÍDEO (1 crédito = 1 vídeo voz padrão) */}
      <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        ≈ R$ {pricePerCredit} por vídeo com voz padrão
      </p>

      <button
        type="button"
        onClick={onSelect}
        disabled={selected}
        className="mt-6 w-full py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 cursor-pointer disabled:opacity-50"
        style={{
          background: highlight
            ? 'linear-gradient(135deg, #ff5638, #3e9bff)'
            : 'var(--bg-raised)',
          color: '#fff',
          border: highlight ? 'none' : '1px solid var(--border-subtle)',
        }}
      >
        {selected ? 'Selecionado' : `Escolher ${displayName}`}
      </button>
    </div>
  )
}
