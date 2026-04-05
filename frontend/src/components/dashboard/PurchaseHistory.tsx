'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHistory, type PurchaseHistoryItem } from '@/lib/payments'
import { InlineError } from '@/components/ui/feedback'

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  approved: { label: 'Aprovado', color: '#22c55e' },
  pending: { label: 'Pendente', color: '#eab308' },
  rejected: { label: 'Rejeitado', color: '#ef4444' },
}

export default function PurchaseHistory() {
  const [purchases, setPurchases] = useState<PurchaseHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)

  const loadHistory = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      const data = await fetchHistory()
      if (mountedRef.current) setPurchases(data)
    } catch (err) {
      if (mountedRef.current) setError(err instanceof Error ? err.message : 'Erro ao carregar histórico')
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    loadHistory()
    return () => { mountedRef.current = false }
  }, [loadHistory])

  if (loading) {
    return (
      <div className="animate-pulse space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 rounded-lg" style={{ background: 'var(--bg-surface)' }} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <InlineError
        title="Não foi possível carregar o histórico"
        description={error}
        onRetry={loadHistory}
      />
    )
  }

  if (purchases.length === 0) {
    return (
      <p className="text-sm text-center py-8" style={{ color: 'var(--text-tertiary)' }}>
        Nenhuma compra realizada ainda.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border-subtle)' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: 'var(--bg-surface)' }}>
            <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--text-secondary)' }}>Data</th>
            <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--text-secondary)' }}>Pacote</th>
            <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--text-secondary)' }}>Créditos</th>
            <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--text-secondary)' }}>Valor</th>
            <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--text-secondary)' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {purchases.map((p) => {
            const st = STATUS_LABELS[p.status] || { label: p.status, color: 'var(--text-tertiary)' }
            const date = new Date(p.created_at).toLocaleDateString('pt-BR')
            const price = `R$ ${(p.price_brl / 100).toFixed(2).replace('.', ',')}`
            return (
              <tr key={p.id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <td className="px-4 py-3" style={{ color: 'var(--text-primary)' }}>{date}</td>
                <td className="px-4 py-3 capitalize" style={{ color: 'var(--text-primary)' }}>{p.package_name}</td>
                <td className="px-4 py-3 text-center" style={{ color: 'var(--accent-primary, #a855f7)' }}>{p.credits_amount}</td>
                <td className="px-4 py-3 text-right" style={{ color: 'var(--text-primary)' }}>{price}</td>
                <td className="px-4 py-3 text-center">
                  <span
                    className="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                    style={{ backgroundColor: `${st.color}20`, color: st.color }}
                  >
                    {st.label}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
