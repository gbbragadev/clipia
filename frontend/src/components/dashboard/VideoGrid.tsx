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
    <div className="rounded-xl bg-[#1A1A1A] border border-[#222] overflow-hidden animate-pulse">
      <div className="aspect-video bg-[#222]" />
      <div className="p-4 space-y-2">
        <div className="h-4 bg-[#222] rounded w-3/4" />
        <div className="h-3 bg-[#222] rounded w-1/2" />
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
