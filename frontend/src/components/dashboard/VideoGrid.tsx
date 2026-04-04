'use client'

import type { JobSummary } from '@/lib/editor-api'
import VideoCard from './VideoCard'
import EmptyState from './EmptyState'

interface VideoGridProps {
  jobs: JobSummary[]
  loading: boolean
  onEdit: (jobId: string) => void
}

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

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {jobs.map((job) => (
        <VideoCard key={job.job_id} job={job} onEdit={onEdit} />
      ))}
    </div>
  )
}
