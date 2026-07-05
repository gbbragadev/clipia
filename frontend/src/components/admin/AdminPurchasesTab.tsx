'use client'

import { useCallback, useEffect, useState } from 'react'

import { fetchAdminPurchases, type AdminPurchaseItem } from '@/lib/admin'
import { InlineError } from '@/components/ui/feedback'
import { AdminPager, AdminTable, StatusPill, formatAdminDateTime } from './AdminTable'

const PAGE_SIZE = 50
const STATUS_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'pending', label: 'Pendentes' },
  { value: 'approved', label: 'Aprovadas' },
  { value: 'refunded', label: 'Estornadas' },
]

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100)
}

export default function AdminPurchasesTab() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [purchases, setPurchases] = useState<AdminPurchaseItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAdminPurchases({ status, page })
      setPurchases(data.purchases)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar compras')
    } finally {
      setLoading(false)
    }
  }, [status, page])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return <InlineError title="Não foi possível carregar as compras" description={error} onRetry={() => load()} />
  }

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Compras</h2>
        <div className="flex gap-2">
          {STATUS_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => {
                setPage(1)
                setStatus(option.value)
              }}
              className="rounded-full px-3 py-1.5 text-sm transition"
              style={{
                background: status === option.value ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.04)',
                color: status === option.value ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        {loading ? (
          <div className="h-40 animate-pulse rounded-2xl" style={{ background: 'rgba(255,255,255,0.04)' }} />
        ) : (
          <AdminTable
            columns={['Quando', 'Usuário', 'Pacote', 'Créditos', 'Valor', 'Provedor', 'Status']}
            rows={purchases.map((purchase) => [
              <span key={purchase.id}>{formatAdminDateTime(purchase.created_at)}</span>,
              <span key={`${purchase.id}-email`} className="text-xs">{purchase.user_email}</span>,
              <span key={`${purchase.id}-pkg`} className="capitalize font-medium">{purchase.package_name}</span>,
              <span key={`${purchase.id}-credits`}>
                {purchase.credits_amount}
                {purchase.bonus_credits > 0 && (
                  <span className="ml-1 text-xs" style={{ color: '#4ade80' }}>+{purchase.bonus_credits} bônus</span>
                )}
              </span>,
              <span key={`${purchase.id}-price`} className="font-semibold">{formatCurrency(purchase.price_brl)}</span>,
              <span key={`${purchase.id}-provider`} className="text-xs capitalize">{purchase.provider}</span>,
              <StatusPill key={`${purchase.id}-status`} value={purchase.status} />,
            ])}
          />
        )}
      </div>

      <AdminPager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
