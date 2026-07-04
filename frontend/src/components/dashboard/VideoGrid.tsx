'use client'

import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { fadeUp, staggerContainer, useReducedMotionState } from '@/lib/motion'
import { ACTIVE_JOB_STATUSES, type JobSummary } from '@/lib/editor-api'
import VideoCard from './VideoCard'
import EmptyState from './EmptyState'
import FilterBar from './FilterBar'

interface VideoGridProps {
  jobs: JobSummary[]
  loading: boolean
  onEdit: (jobId: string) => void
  onCancel?: (jobId: string) => void
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

export default function VideoGrid({ jobs, loading, onEdit, onCancel }: VideoGridProps) {
  const reduceMotion = useReducedMotionState()
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
    if (statusFilter === 'processing') {
      // "Processando" agrupa todos os status ativos (queued/processing/rendering/cancelling)
      result = result.filter((j) => ACTIVE_JOB_STATUSES.includes(j.status))
    } else if (statusFilter !== 'all') {
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
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
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
    ...(ACTIVE_JOB_STATUSES.some((s) => statusCounts[s]) ? [{ value: 'processing', label: 'Processando', count: ACTIVE_JOB_STATUSES.reduce((acc, s) => acc + (statusCounts[s] || 0), 0) }] : []),
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
      <motion.div
        className="grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4"
        variants={staggerContainer(0.05)}
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
      >
        {filteredJobs.map((job) => (
          <motion.div key={job.job_id} variants={fadeUp}>
            <VideoCard job={job} onEdit={onEdit} onCancel={onCancel} />
          </motion.div>
        ))}
      </motion.div>
      {filteredJobs.length === 0 && (
        <p className="text-center py-8 text-sm" style={{ color: 'var(--text-tertiary)' }}>
          Nenhum vídeo com esse filtro.
        </p>
      )}
    </div>
  )
}
