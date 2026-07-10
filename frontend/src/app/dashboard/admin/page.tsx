'use client'

import Link from 'next/link'
import { useEffect, useState, type ReactNode } from 'react'

import { useAuth } from '@/contexts/AuthContext'
import { fetchAdminDashboard, type AdminDashboardResponse, type AdminRange, type AdminSeriesPoint } from '@/lib/admin'
import { InlineError } from '@/components/ui/feedback'
import AdminFeedbackTab from '@/components/admin/AdminFeedbackTab'
import AdminJobsTab from '@/components/admin/AdminJobsTab'
import AdminPurchasesTab from '@/components/admin/AdminPurchasesTab'
import AdminUsersTab from '@/components/admin/AdminUsersTab'

const RANGE_OPTIONS: Array<{ value: AdminRange; label: string }> = [
  { value: '7d', label: '7 dias' },
  { value: '30d', label: '30 dias' },
  { value: '90d', label: '90 dias' },
]

type AdminTabKey = 'overview' | 'users' | 'purchases' | 'jobs' | 'feedback'

const TAB_OPTIONS: Array<{ value: AdminTabKey; label: string }> = [
  { value: 'overview', label: 'Visão geral' },
  { value: 'users', label: 'Usuários' },
  { value: 'purchases', label: 'Compras' },
  { value: 'jobs', label: 'Vídeos' },
  { value: 'feedback', label: 'Feedback' },
]

export default function AdminDashboardPage() {
  const { user } = useAuth()
  const [range, setRange] = useState<AdminRange>('30d')
  const [tab, setTab] = useState<AdminTabKey>('overview')
  const [data, setData] = useState<AdminDashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (user?.plan !== 'admin') {
      setLoading(false)
      return
    }

    let active = true

    async function loadDashboard() {
      setLoading(true)
      setError(null)
      try {
        const next = await fetchAdminDashboard(range)
        if (active) setData(next)
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Não foi possível carregar o painel')
      } finally {
        if (active) setLoading(false)
      }
    }

    loadDashboard()
    return () => {
      active = false
    }
  }, [range, user?.plan])

  if (user?.plan !== 'admin') {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <InlineError
          title="Acesso administrativo restrito"
          description="Esta área é exclusiva para usuários administradores."
        />
      </div>
    )
  }

  const overview = loading ? (
    <div className="space-y-6">
      <div className="card p-6 animate-pulse">
        <div className="h-6 w-40 rounded bg-white/10 mb-3" />
        <div className="h-4 w-64 rounded bg-white/10" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="card p-5 animate-pulse">
            <div className="h-3 w-24 rounded bg-white/10 mb-4" />
            <div className="h-7 w-28 rounded bg-white/10 mb-3" />
            <div className="h-3 w-20 rounded bg-white/10" />
          </div>
        ))}
      </div>
    </div>
  ) : error || !data ? (
    <InlineError
      title="Não foi possível carregar o painel administrativo"
      description={error || 'Sem dados disponíveis'}
    />
  ) : (
    <>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Receita aprovada" value={formatCurrency(data.summary.approved_revenue_brl)} hint={`${data.summary.approved_orders} pedidos aprovados`} accent="#22c55e" />
        <StatCard title="Receita pendente" value={formatCurrency(data.summary.pending_revenue_brl)} hint={`${data.summary.pending_orders} pagamentos em aberto`} accent="#f59e0b" />
        <StatCard title="Ticket médio" value={formatCurrency(data.summary.average_ticket_brl)} hint={`${data.summary.credits_sold} créditos vendidos`} accent="#38bdf8" />
        <StatCard title="Usuários novos" value={String(data.summary.new_users)} hint={`${data.summary.verified_users} verificados / ${data.summary.paying_users} pagantes`} accent="#3e9bff" />
        <StatCard title="Jobs ativos" value={String(data.summary.active_jobs)} hint="fila + processamento agora" accent="#fb7185" />
        <StatCard title="Créditos consumidos" value={String(data.summary.credits_consumed)} hint="estimado pelo volume de jobs" accent="#f97316" />
        <StatCard title="Taxa de sucesso" value={`${data.operations.success_rate}%`} hint={`${data.operations.completed_jobs} concluídos / ${data.operations.failed_jobs} falhos`} accent="#14b8a6" />
        <StatCard title="Storage total" value={`${formatCompactGb(data.operations.jobs_dir_size_gb + data.operations.output_dir_size_gb)} GB`} hint={`${data.operations.orphan_dirs} diretórios órfãos`} accent="#ff7a61" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="card p-6">
          <PanelHeader
            eyebrow="Receita"
            title="Faturamento por dia"
            description="Compras aprovadas convertidas em receita realizada."
          />
          <MiniBarChart data={data.timeseries.revenue_by_day} color="linear-gradient(180deg, #22c55e, #15803d)" formatter={(value) => formatCurrency(value)} />
        </div>
        <div className="card p-6">
          <PanelHeader
            eyebrow="Funil"
            title="Cadastro ate pagamento"
            description="Conversao dos novos usuarios dentro da janela selecionada."
          />
          <FunnelCard data={data.funnel} />
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_1.1fr_0.9fr]">
        <div className="card p-6">
          <PanelHeader
            eyebrow="Aquisicao"
            title="Novos usuarios por dia"
            description="Volume de entrada no produto."
          />
          <MiniBarChart data={data.timeseries.new_users_by_day} color="linear-gradient(180deg, #60a5fa, #2563eb)" formatter={(value) => `${value} usuarios`} />
        </div>
        <div className="card p-6">
          <PanelHeader
            eyebrow="Produção"
            title="Jobs criados por dia"
            description="Carga operacional da plataforma."
          />
          <MiniBarChart data={data.timeseries.jobs_by_day} color="linear-gradient(180deg, #f97316, #ea580c)" formatter={(value) => `${value} jobs`} />
        </div>
        <div className="card p-6">
          <PanelHeader
            eyebrow="Mix"
            title="Pacotes vendidos"
            description="Composicao de receita por oferta."
          />
          <div className="mt-4 space-y-3">
            {data.package_mix.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Nenhuma venda no periodo.</p>
            ) : (
              data.package_mix.map((item) => (
                <div key={item.package_name} className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-subtle)', background: 'rgba(255,255,255,0.02)' }}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium capitalize">{item.package_name}</p>
                      <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.orders} pedidos</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold">{formatCurrency(item.approved_revenue_brl)}</p>
                      <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.credits_sold} creditos</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="card p-6">
          <PanelHeader
            eyebrow="Operacao"
            title="Saude operacional"
            description="Fila, falhas, custo pendente e ocupacao de storage."
          />
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <MetricRow label="Jobs em fila" value={String(data.operations.queued_jobs)} />
            <MetricRow label="Jobs processando" value={String(data.operations.processing_jobs)} />
            <MetricRow label="Jobs concluídos" value={String(data.operations.completed_jobs)} />
            <MetricRow label="Jobs falhos" value={String(data.operations.failed_jobs)} />
            <MetricRow label="Creditos pendentes medios" value={String(data.operations.avg_pending_credits)} />
            <MetricRow label="Diretorio de jobs" value={`${formatCompactGb(data.operations.jobs_dir_size_gb)} GB`} />
            <MetricRow label="Diretorio de output" value={`${formatCompactGb(data.operations.output_dir_size_gb)} GB`} />
            <MetricRow label="Job mais antigo" value={`${data.operations.oldest_job_days} dias`} />
          </div>
        </div>
        <div className="card p-6">
          <PanelHeader
            eyebrow="Atalhos"
            title="Acoes rapidas"
            description="Acessos operacionais frequentes."
          />
          <div className="mt-5 flex flex-col gap-3">
            <Link href="/dashboard" className="btn-outline text-center">Voltar ao dashboard do cliente</Link>
            <Link href="/dashboard/credits" className="btn-outline text-center">Abrir area de creditos</Link>
            <Link href="/dashboard/settings" className="btn-outline text-center">Configurar conta admin</Link>
          </div>
          <div className="mt-5 rounded-2xl border p-4" style={{ borderColor: 'rgba(34,197,94,0.2)', background: 'rgba(34,197,94,0.08)' }}>
            <p className="text-xs uppercase tracking-[0.18em]" style={{ color: '#86efac' }}>Leitura operacional</p>
            <p className="mt-2 text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
              Este painel trata gastos como custo operacional observavel: volume de jobs, creditos-base consumidos, pendencias de edicao e storage.
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <ActivityTable
          title="Usuarios recentes"
          columns={['Usuario', 'Status', 'Entrada']}
          rows={data.recent_activity.recent_users.map((item) => [
            <div key={item.id}>
              <p className="font-medium">{item.name}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.email}</p>
            </div>,
            <span key={`${item.id}-status`} className="text-xs">
              {item.is_paying ? 'Pagante' : item.email_verified ? 'Verificado' : 'Pendente'}
            </span>,
            <span key={`${item.id}-created`} className="text-sm">{formatDateTime(item.created_at)}</span>,
          ])}
        />
        <ActivityTable
          title="Compras recentes"
          columns={['Pacote', 'Status', 'Valor']}
          rows={data.recent_activity.recent_purchases.map((item) => [
            <div key={item.id}>
              <p className="font-medium capitalize">{item.package_name}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.credits_amount} creditos</p>
            </div>,
            <span key={`${item.id}-status`} className="text-xs uppercase">{item.status}</span>,
            <span key={`${item.id}-value`} className="text-sm">{formatCurrency(item.price_brl / 100)}</span>,
          ])}
        />
        <ActivityTable
          title="Falhas recentes"
          columns={['Job', 'Erro', 'Quando']}
          rows={data.recent_activity.recent_failed_jobs.map((item) => [
            <div key={item.id}>
              <p className="font-medium line-clamp-2">{item.topic}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.id.slice(0, 8)}</p>
            </div>,
            <span key={`${item.id}-error`} className="text-xs line-clamp-2">{item.error || 'Sem detalhe'}</span>,
            <span key={`${item.id}-created`} className="text-sm">{formatDateTime(item.created_at)}</span>,
          ])}
        />
      </section>
    </>
  )

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <section className="card p-6 overflow-hidden relative">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(circle at top right, rgba(34,197,94,0.16), transparent 30%), radial-gradient(circle at left, rgba(59,130,246,0.14), transparent 35%)',
          }}
        />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em]" style={{ color: '#86efac' }}>Admin Control</p>
            <h1 className="mt-2 text-3xl font-semibold">Painel administrativo do SaaS</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
              Receita, conversao, saude operacional e carga do produto em uma unica superficie.
            </p>
          </div>
          {tab === 'overview' && (
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-2xl border px-4 py-3" style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)' }}>
                <p className="text-[11px] uppercase tracking-[0.18em]" style={{ color: 'var(--text-tertiary)' }}>Janela</p>
                <div className="mt-2 flex gap-2">
                  {RANGE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => setRange(option.value)}
                      className="rounded-full px-3 py-1.5 text-sm transition"
                      style={{
                        background: range === option.value ? 'linear-gradient(135deg, #16a34a, #0ea5e9)' : 'rgba(255,255,255,0.04)',
                        color: range === option.value ? '#fff' : 'var(--text-secondary)',
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              {data && (
                <div className="rounded-2xl border px-4 py-3 text-sm" style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)' }}>
                  <p style={{ color: 'var(--text-tertiary)' }}>Periodo analisado</p>
                  <p className="mt-1 font-medium">{formatDate(data.window_start)} a {formatDate(data.window_end)}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <nav className="flex flex-wrap gap-2" aria-label="Seções do painel">
        {TAB_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => setTab(option.value)}
            aria-pressed={tab === option.value}
            className="rounded-full px-4 py-2 text-sm font-medium transition"
            style={{
              background: tab === option.value ? 'linear-gradient(135deg, #ff5638, #3e9bff)' : 'rgba(255,255,255,0.04)',
              color: tab === option.value ? '#fff' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {option.label}
          </button>
        ))}
      </nav>

      {tab === 'overview' && overview}
      {tab === 'users' && <AdminUsersTab />}
      {tab === 'purchases' && <AdminPurchasesTab />}
      {tab === 'jobs' && <AdminJobsTab />}
      {tab === 'feedback' && <AdminFeedbackTab />}
    </div>
  )
}

function PanelHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.18em]" style={{ color: 'var(--text-tertiary)' }}>{eyebrow}</p>
      <h2 className="mt-2 text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>{description}</p>
    </div>
  )
}

function StatCard({ title, value, hint, accent }: { title: string; value: string; hint: string; accent: string }) {
  return (
    <div className="card p-5">
      <div className="h-1.5 w-14 rounded-full" style={{ background: accent }} />
      <p className="mt-4 text-xs uppercase tracking-[0.16em]" style={{ color: 'var(--text-tertiary)' }}>{title}</p>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
      <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>{hint}</p>
    </div>
  )
}

function FunnelCard({ data }: { data: AdminDashboardResponse['funnel'] }) {
  const stages = [
    { label: 'Cadastrados', value: data.registered, tone: '#60a5fa' },
    { label: 'Verificados', value: data.verified, tone: '#f59e0b' },
    { label: 'Pagantes', value: data.paying, tone: '#22c55e' },
  ]
  const max = Math.max(...stages.map((stage) => stage.value), 1)

  return (
    <div className="mt-6 space-y-4">
      {stages.map((stage) => (
        <div key={stage.label}>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span style={{ color: 'var(--text-secondary)' }}>{stage.label}</span>
            <span className="font-medium">{stage.value}</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <div className="h-full rounded-full" style={{ width: `${(stage.value / max) * 100}%`, background: stage.tone }} />
          </div>
        </div>
      ))}
      <div className="grid gap-3 pt-2 sm:grid-cols-2">
        <MetricRow label="Taxa de verificacao" value={`${data.verification_rate}%`} compact />
        <MetricRow label="Conversao em pagante" value={`${data.payer_conversion_rate}%`} compact />
      </div>
    </div>
  )
}

function MiniBarChart({
  data,
  color,
  formatter,
}: {
  data: AdminSeriesPoint[]
  color: string
  formatter: (value: number) => string
}) {
  const max = Math.max(...data.map((point) => point.value), 1)

  return (
    <div className="mt-6">
      <div className="flex h-52 items-end gap-2">
        {data.map((point) => {
          const safeHeight = point.value === 0 ? 6 : Math.max((point.value / max) * 100, 8)
          return (
            <div key={point.date} className="group flex min-w-0 flex-1 flex-col items-center justify-end">
              <div className="mb-2 text-[11px] opacity-0 transition group-hover:opacity-100" style={{ color: 'var(--text-secondary)' }}>
                {formatter(point.value)}
              </div>
              <div
                className="w-full rounded-t-2xl transition group-hover:opacity-80"
                style={{ height: `${safeHeight}%`, background: color, minHeight: 6 }}
              />
              <span className="mt-2 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                {shortDate(point.date)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function MetricRow({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) {
  return (
    <div className="rounded-2xl border px-4 py-3" style={{ borderColor: 'var(--border-subtle)', background: 'rgba(255,255,255,0.02)' }}>
      <p className={`text-xs uppercase tracking-[0.16em] ${compact ? '' : 'mb-2'}`} style={{ color: 'var(--text-tertiary)' }}>{label}</p>
      <p className={`${compact ? 'mt-2' : ''} text-lg font-semibold`}>{value}</p>
    </div>
  )
}

function ActivityTable({
  title,
  columns,
  rows,
}: {
  title: string
  columns: string[]
  rows: ReactNode[][]
}) {
  return (
    <div className="card p-6">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[16rem] sm:min-w-[18rem] text-left">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} className="pb-3 text-xs uppercase tracking-[0.16em]" style={{ color: 'var(--text-tertiary)' }}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-4 text-xs sm:text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Nenhum registro disponível.
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={rowIndex} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="py-3 pr-3 align-top text-xs sm:text-sm">{cell}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

function formatDate(value: string | null): string {
  if (!value) return '-'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
}

function formatDateTime(value: string | null): string {
  if (!value) return '-'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function shortDate(value: string): string {
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' }).format(new Date(value))
}

function formatCompactGb(value: number): string {
  return value.toFixed(value >= 10 ? 1 : 2)
}
