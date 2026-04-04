'use client'

import { useMemo, useState } from 'react'
import type { JobSummary } from '@/lib/editor-api'
import VideoCard from './VideoCard'
import EmptyState from './EmptyState'
import FilterBar from './FilterBar'

interface VideoGridProps {
  jobs: JobSummary[]
  loading: boolean
  onEdit: (jobId: string) => void
}

type SortOrder = 'newest' | 'oldest'
type StatusFilter = 'all' | 'editable' | 'completed' | 'queued' | 'processing' | 'error'

function SkeletonCard() {
  return (
    <div className="rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden animate-pulse">
      <div className="aspect-video bg-[var(--bg-surface-hover)]" />
      <div className="p-4 space-y-2">
        <div className="h-4 bg-[var(--bg-surface-hover)] rounded w-3/4" />
        <div className="h-3 bg-[var(--bg-surface-hover)] rounded w-1/2" />
      </div>
    </div>
  )
}

export default function VideoGrid({ jobs, loading, onEdit }: VideoGridProps) {
  const [sort, setSort] = useState<SortOrder>('newest')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const j of jobs) {
      const s = j.status || 'unknown'
      counts[s] = (counts[s] || 0) + 1
    }
    return counts
  }, [jobs])

  const filteredJobs = useMemo(() => {
    let result = [...jobs]
    if (statusFilter !== 'all') {
      result = result.filter((j) => j.status === statusFilter)
    }
    result.sort((a, b) => {
      const da = a.created_at || ''
      const db = b.created_at || ''
      return sort === 'newest' ? db.localeCompare(da) : da.localeCompare(db)
    })
    return result
  }, [jobs, sort, statusFilter])

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  if (jobs.length === 0) {
    return <EmptyState />
  }

  const statusOptions = [
    { value: 'all', label: 'Todos', count: jobs.length },
    ...(statusCounts['editable'] ? [{ value: 'editable', label: 'Concluídos', count: statusCounts['editable'] }] : []),
    ...(statusCounts['completed'] ? [{ value: 'completed', label: 'Concluídos', count: (statusCounts['completed'] || 0) + (statusCounts['editable'] || 0) }] : []),
    ...(statusCounts['processing'] || statusCounts['queued'] ? [{ value: 'processing', label: 'Processando', count: (statusCounts['processing'] || 0) + (statusCounts['queued'] || 0) }] : []),
    ...(statusCounts['error'] || statusCounts['failed'] ? [{ value: 'error', label: 'Erro', count: (statusCounts['error'] || 0) + (statusCounts['failed'] || 0) }] : []),
  ]

  return (
    <div>
      <FilterBar
        filters={[
          {
            label: 'Ordenar',
            options: [
              { value: 'newest', label: 'Recentes' },
              { value: 'oldest', label: 'Antigos' },
            ],
            value: sort,
            onChange: (v) => setSort(v as SortOrder),
          },
          {
            label: 'Status',
            options: statusOptions,
            value: statusFilter,
            onChange: (v) => setStatusFilter(v as StatusFilter),
          },
        ]}
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredJobs.map((job) => (
          <VideoCard key={job.job_id} job={job} onEdit={onEdit} />
        ))}
      </div>
      {filteredJobs.length === 0 && (
        <p className="text-center py-8 text-sm" style={{ color: 'var(--text-tertiary)' }}>
          Nenhum vídeo com esse filtro.
        </p>
      )}
    </div>
  )
}
