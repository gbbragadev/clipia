'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { fetchPackages, type CreditPackage } from '@/lib/payments'
import CreditPackageCard from '@/components/dashboard/CreditPackageCard'
import PurchaseHistory from '@/components/dashboard/PurchaseHistory'

const TOAST_MESSAGES: Record<string, { text: string; type: 'success' | 'error' | 'info' }> = {
  success: { text: 'Pagamento aprovado! Seus créditos foram adicionados.', type: 'success' },
  failure: { text: 'Pagamento não aprovado. Tente novamente.', type: 'error' },
  pending: { text: 'Pagamento pendente. Seus créditos serão adicionados assim que confirmado.', type: 'info' },
}

const TOAST_COLORS = {
  success: { bg: 'rgba(34, 197, 94, 0.15)', border: '#22c55e', text: '#22c55e' },
  error: { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#ef4444' },
  info: { bg: 'rgba(234, 179, 8, 0.15)', border: '#eab308', text: '#eab308' },
}

export default function CreditsPage() {
  const { user, refreshUser } = useAuth()
  const searchParams = useSearchParams()
  const [packages, setPackages] = useState<CreditPackage[]>([])
  const [toast, setToast] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null)

  useEffect(() => {
    fetchPackages().then(setPackages).catch(console.error)
  }, [])

  // Handle return from MercadoPago
  useEffect(() => {
    const status = searchParams.get('status')
    if (status && TOAST_MESSAGES[status]) {
      setToast(TOAST_MESSAGES[status])
      refreshUser()
      // Clear params after showing
      const timeout = setTimeout(() => setToast(null), 6000)
      return () => clearTimeout(timeout)
    }
  }, [searchParams, refreshUser])

  const toastColors = toast ? TOAST_COLORS[toast.type] : null

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Toast */}
      {toast && toastColors && (
        <div
          className="mb-6 px-4 py-3 rounded-xl text-sm font-medium"
          style={{
            background: toastColors.bg,
            border: `1px solid ${toastColors.border}`,
            color: toastColors.text,
          }}
        >
          {toast.text}
        </div>
      )}

      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Meus Créditos
        </h1>
        <div className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-full" style={{ background: 'var(--bg-surface)' }}>
          <span className="text-3xl font-bold" style={{ color: 'var(--accent-primary, #a855f7)' }}>
            {user?.credits ?? 0}
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>créditos disponíveis</span>
        </div>
      </div>

      {/* Packages */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
        {packages.map((pkg) => (
          <CreditPackageCard
            key={pkg.id}
            pkg={pkg}
            highlight={pkg.id === 'popular'}
            badge={pkg.id === 'popular' ? 'Mais vendido' : pkg.id === 'pro' ? 'Melhor custo' : undefined}
          />
        ))}
      </div>

      {/* History */}
      <div>
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Histórico de compras
        </h2>
        <PurchaseHistory />
      </div>
    </div>
  )
}
