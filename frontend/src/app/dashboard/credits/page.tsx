'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { fetchPackages, type CreditPackage, type PaymentProvider } from '@/lib/payments'
import CreditPackageCard from '@/components/dashboard/CreditPackageCard'
import PurchaseHistory from '@/components/dashboard/PurchaseHistory'
import { InlineError } from '@/components/ui/feedback'
import { useToast } from '@/components/ui/feedback'

export default function CreditsPage() {
  const { user, refreshUser } = useAuth()
  const { success, error, info } = useToast()
  const searchParams = useSearchParams()
  const [packages, setPackages] = useState<CreditPackage[]>([])
  const [loadingPackages, setLoadingPackages] = useState(true)
  const [packagesError, setPackagesError] = useState<string | null>(null)
  const [provider, setProvider] = useState<PaymentProvider>('mercadopago')
  const mountedRef = useRef(true)

  const loadPackages = useCallback(async () => {
    setLoadingPackages(true)
    setPackagesError(null)
    try {
      const data = await fetchPackages()
      if (mountedRef.current) setPackages(data)
    } catch (err) {
      if (mountedRef.current) setPackagesError(err instanceof Error ? err.message : 'Erro ao carregar pacotes')
    } finally {
      if (mountedRef.current) setLoadingPackages(false)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    loadPackages()
    return () => { mountedRef.current = false }
  }, [loadPackages])

  // Handle return from MercadoPago
  useEffect(() => {
    const status = searchParams.get('status')
    if (status === 'success') {
      success('Pagamento aprovado', 'Seus créditos foram adicionados.')
      refreshUser()
    } else if (status === 'failure') {
      error('Pagamento não aprovado', 'Tente novamente.')
    } else if (status === 'pending') {
      info('Pagamento pendente', 'Seus créditos serão adicionados assim que confirmado.')
      refreshUser()
    }
  }, [error, info, refreshUser, searchParams, success])

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {packagesError ? (
        <InlineError
          title="Não foi possível carregar os pacotes"
          description={packagesError}
          onRetry={() => loadPackages()}
        />
      ) : (
        <>
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              Meus Créditos
            </h1>
            <div className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-full" style={{ background: 'var(--bg-surface)' }}>
              <span className="text-3xl font-bold" style={{ color: 'var(--accent-primary, #ff5638)' }}>
                {user?.credits ?? 0}
              </span>
              <span style={{ color: 'var(--text-secondary)' }}>créditos disponíveis</span>
            </div>
          </div>

          {/* Provider selector */}
          <div className="flex justify-center gap-2 mb-6">
            {([
              { id: 'mercadopago', label: 'Mercado Pago', sub: 'Pix, cartão e boleto' },
              { id: 'stripe', label: 'Stripe', sub: 'Cartão e Pix' },
            ] as const).map((opt) => (
              <button
                key={opt.id}
                onClick={() => setProvider(opt.id)}
                aria-pressed={provider === opt.id}
                className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer"
                style={{
                  background: provider === opt.id ? 'var(--bg-raised)' : 'transparent',
                  border: provider === opt.id
                    ? '1px solid var(--accent-primary, #ff5638)'
                    : '1px solid var(--border-subtle)',
                  color: provider === opt.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                }}
              >
                {opt.label}
                <span className="block text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{opt.sub}</span>
              </button>
            ))}
          </div>

          {/* Packages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
            {loadingPackages ? (
              <div className="md:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card h-64 animate-pulse" />
                <div className="card h-64 animate-pulse" />
                <div className="card h-64 animate-pulse" />
              </div>
            ) : (
              packages.map((pkg) => (
                <CreditPackageCard
                  key={pkg.id}
                  pkg={pkg}
                  provider={provider}
                  highlight={pkg.id === 'popular'}
                  badge={pkg.id === 'popular' ? 'Mais Popular' : pkg.id === 'pro' ? 'Melhor custo' : undefined}
                />
              ))
            )}
          </div>

          {/* History */}
          <div>
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Histórico de compras
            </h2>
            <PurchaseHistory />
          </div>
        </>
      )}
    </div>
  )
}
