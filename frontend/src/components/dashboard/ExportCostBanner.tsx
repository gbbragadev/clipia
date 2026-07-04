'use client'

interface ExportCostBannerProps {
  pendingCredits: number
  userCredits: number
}

export default function ExportCostBanner({ pendingCredits, userCredits }: ExportCostBannerProps) {
  if (pendingCredits <= 0) return null

  const canAfford = userCredits >= pendingCredits

  return (
    <div
      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-3 rounded-xl text-sm"
      style={{
        background: canAfford ? 'rgba(255, 86, 56, 0.1)' : 'rgba(239, 68, 68, 0.1)',
        border: `1px solid ${canAfford ? 'rgba(255, 86, 56, 0.25)' : 'rgba(239, 68, 68, 0.25)'}`,
      }}
    >
      <div>
        <span style={{ color: canAfford ? '#ff7a61' : '#fca5a5' }}>
          Custo de edição IA: <strong>{pendingCredits}</strong> crédito{pendingCredits !== 1 ? 's' : ''}
        </span>
        <span className="ml-2" style={{ color: 'var(--text-tertiary)' }}>
          (Você tem {userCredits})
        </span>
      </div>
      {!canAfford && (
        <a
          href="/dashboard/credits"
          className="px-3 py-1 rounded-lg text-xs font-semibold"
          style={{
            background: 'linear-gradient(135deg, #ff5638, #3e9bff)',
            color: '#fff',
            textDecoration: 'none',
          }}
        >
          Comprar créditos
        </a>
      )}
    </div>
  )
}
