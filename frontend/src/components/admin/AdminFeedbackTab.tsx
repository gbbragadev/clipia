'use client'

import { useCallback, useEffect, useState } from 'react'
import { Star } from 'lucide-react'

import { fetchAdminFeedbacks, type AdminFeedbackItem } from '@/lib/admin'
import { InlineError } from '@/components/ui/feedback'
import { AdminPager, AdminTable, formatAdminDateTime } from './AdminTable'

const PAGE_SIZE = 50
const KIND_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'widget', label: 'Widget' },
  { value: 'post_video', label: 'Pós-vídeo' },
]

function RatingStars({ rating }: { rating: number | null }) {
  if (rating === null) return <span style={{ color: 'var(--text-tertiary)' }}>-</span>
  return (
    <span className="flex gap-0.5" aria-label={`Nota ${rating} de 5`}>
      {[1, 2, 3, 4, 5].map((value) => (
        <Star
          key={value}
          size={13}
          fill={rating >= value ? '#fbbf24' : 'transparent'}
          color={rating >= value ? '#fbbf24' : 'var(--text-tertiary)'}
        />
      ))}
    </span>
  )
}

export default function AdminFeedbackTab() {
  const [kind, setKind] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [feedbacks, setFeedbacks] = useState<AdminFeedbackItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAdminFeedbacks({ kind, page })
      setFeedbacks(data.feedbacks)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar feedbacks')
    } finally {
      setLoading(false)
    }
  }, [kind, page])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return <InlineError title="Não foi possível carregar os feedbacks" description={error} onRetry={() => load()} />
  }

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Feedback dos usuários</h2>
        <div className="flex gap-2">
          {KIND_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => {
                setPage(1)
                setKind(option.value)
              }}
              className="rounded-full px-3 py-1.5 text-sm transition"
              style={{
                background: kind === option.value ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.04)',
                color: kind === option.value ? 'var(--text-primary)' : 'var(--text-secondary)',
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
            columns={['Quando', 'Usuário', 'Tipo', 'Nota', 'Comentário', 'Contexto']}
            emptyText="Nenhum feedback ainda — divulgue o widget!"
            rows={feedbacks.map((item) => [
              <span key={item.id}>{formatAdminDateTime(item.created_at)}</span>,
              <span key={`${item.id}-email`} className="text-xs">{item.user_email}</span>,
              <span key={`${item.id}-kind`} className="text-xs uppercase" style={{ color: 'var(--text-secondary)' }}>
                {item.kind === 'widget' ? 'Widget' : 'Pós-vídeo'}
              </span>,
              <RatingStars key={`${item.id}-rating`} rating={item.rating} />,
              <p key={`${item.id}-comment`} className="max-w-[20rem] whitespace-pre-wrap">
                {item.comment || <span style={{ color: 'var(--text-tertiary)' }}>-</span>}
              </p>,
              <span key={`${item.id}-ctx`} className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                {item.job_topic || item.source_url || '-'}
              </span>,
            ])}
          />
        )}
      </div>

      <AdminPager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
