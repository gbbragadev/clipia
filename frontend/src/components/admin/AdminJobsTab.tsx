'use client'

import { useCallback, useEffect, useState } from 'react'

import { fetchAdminJobs, type AdminJobItem } from '@/lib/admin'
import { InlineError } from '@/components/ui/feedback'
import { AdminPager, AdminTable, StatusPill, formatAdminDateTime } from './AdminTable'

const PAGE_SIZE = 50
const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'queued', label: 'Na fila' },
  { value: 'processing', label: 'Processando' },
  { value: 'editable', label: 'Editáveis' },
  { value: 'completed', label: 'Concluídos' },
  { value: 'failed', label: 'Falhos' },
]

export default function AdminJobsTab() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [jobs, setJobs] = useState<AdminJobItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAdminJobs({ status, page })
      setJobs(data.jobs)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar vídeos')
    } finally {
      setLoading(false)
    }
  }, [status, page])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return <InlineError title="Não foi possível carregar os vídeos" description={error} onRetry={() => load()} />
  }

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Vídeos</h2>
        <div className="flex flex-wrap gap-2">
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
            columns={['Quando', 'Usuário', 'Tema', 'Template', 'Custo', 'Status']}
            rows={jobs.map((job) => [
              <span key={job.id}>{formatAdminDateTime(job.created_at)}</span>,
              <span key={`${job.id}-email`} className="text-xs">{job.user_email}</span>,
              <div key={`${job.id}-topic`} className="max-w-[18rem]">
                <p className="line-clamp-2">{job.topic}</p>
                {job.error && (
                  <p className="mt-1 text-xs line-clamp-2" style={{ color: '#f87171' }}>{job.error}</p>
                )}
              </div>,
              <span key={`${job.id}-template`} className="text-xs">{job.template_id}</span>,
              <span key={`${job.id}-cost`}>{job.credit_cost}</span>,
              <StatusPill key={`${job.id}-status`} value={job.status} />,
            ])}
          />
        )}
      </div>

      <AdminPager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
