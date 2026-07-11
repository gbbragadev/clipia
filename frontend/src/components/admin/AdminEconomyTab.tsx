'use client'

import { useCallback, useEffect, useState } from 'react'

import { fetchAdminEconomy, type AdminEconomyResponse } from '@/lib/admin'
import { InlineError } from '@/components/ui/feedback'
import { AdminTable, formatAdminDateTime } from './AdminTable'

/** ~R$ por crédito na venda (pacote médio) — referência p/ leitura rápida da margem. */
const CREDIT_VALUE_BRL = 1.3
const USD_BRL = 5.5

function fmtUsd(v: number) {
  return `$${v.toFixed(3)}`
}

function fmtDur(s: number | null) {
  if (s == null) return '—'
  if (s < 90) return `${Math.round(s)}s`
  return `${Math.floor(s / 60)}min${Math.round(s % 60).toString().padStart(2, '0')}`
}

export default function AdminEconomyTab() {
  const [data, setData] = useState<AdminEconomyResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchAdminEconomy())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar a economia')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return <InlineError title="Não foi possível carregar a economia" description={error} onRetry={() => load()} />
  }

  const templates = Object.entries(data?.by_template ?? {})

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <h2 className="text-xl font-semibold">Margem por template</h2>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Custo estimado de API vs créditos cobrados (telemetria gravada no finalize de cada vídeo).
          Jobs anteriores à telemetria não aparecem.
        </p>
        <div className="mt-4">
          {loading ? (
            <div className="h-32 animate-pulse rounded-2xl" style={{ background: 'rgba(255,255,255,0.04)' }} />
          ) : templates.length === 0 ? (
            <p className="py-6 text-sm" style={{ color: 'var(--text-tertiary)' }}>
              Ainda sem dados — gere um vídeo depois deste deploy para a telemetria começar.
            </p>
          ) : (
            <AdminTable
              columns={['Template', 'Vídeos', 'Custo médio (API)', 'Duração média', 'Créditos cobrados', 'Margem est.']}
              rows={templates.map(([tid, agg]) => {
                const revenueBrl = agg.credits * CREDIT_VALUE_BRL
                const costBrl = agg.api_cost_usd_est * USD_BRL
                const margin = revenueBrl - costBrl
                return [
                  tid,
                  String(agg.count),
                  fmtUsd(agg.avg_cost_usd),
                  fmtDur(agg.avg_seconds),
                  String(agg.credits),
                  <span key={tid} style={{ color: margin >= 0 ? 'var(--color-success, #43e0ad)' : 'var(--color-danger, #ff6b6b)' }}>
                    {margin >= 0 ? '+' : ''}R$ {margin.toFixed(2)}
                  </span>,
                ]
              })}
            />
          )}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-xl font-semibold">Últimos vídeos</h2>
        <div className="mt-4">
          {loading ? (
            <div className="h-40 animate-pulse rounded-2xl" style={{ background: 'rgba(255,255,255,0.04)' }} />
          ) : (
            <AdminTable
              columns={['Quando', 'Template', 'Voz', 'Duração total', 'Etapa mais lenta', 'Custo API', 'Créditos', 'Exports']}
              rows={(data?.jobs ?? []).map((job) => {
                const slowest = Object.entries(job.steps).sort((a, b) => b[1] - a[1])[0]
                return [
                  formatAdminDateTime(job.created_at),
                  job.template_id,
                  job.voice_provider,
                  fmtDur(job.total_seconds),
                  slowest ? `${slowest[0]} (${fmtDur(slowest[1])})` : '—',
                  fmtUsd(job.api_cost_usd_est),
                  String(job.credit_cost),
                  job.rerenders ? `${job.rerenders}× (${fmtDur(job.rerender_seconds)})` : '—',
                ]
              })}
            />
          )}
        </div>
      </div>
    </div>
  )
}
