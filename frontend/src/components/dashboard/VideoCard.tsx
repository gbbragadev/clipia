'use client'

import { strings } from '@/lib/strings';
import type { JobSummary } from '@/lib/editor-api'
import { downloadAuthenticatedFile } from '@/lib/download'

const STYLE_GRADIENTS: Record<string, string> = {
  educational: 'from-purple-900/40 to-blue-900/40',
  storytelling: 'from-indigo-900/40 to-violet-900/40',
  news: 'from-slate-800/40 to-gray-900/40',
  comedy: 'from-rose-900/40 to-amber-900/40',
}

const STYLE_ICONS: Record<string, string> = {
  educational: '📚',
  storytelling: '📖',
  news: '📰',
  comedy: '😂',
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed':
    case 'editable':
      return { label: 'Pronto', classes: 'bg-emerald-500/20 text-emerald-400' }
    case 'failed':
    case 'error':
      return { label: 'Erro', classes: 'bg-red-500/20 text-red-400' }
    case 'processing':
      return { label: strings.dashboard.generate.loading, classes: 'bg-purple-500/20 text-purple-400 animate-pulse' }
    case 'queued':
      return { label: 'Na fila', classes: 'bg-gray-500/20 text-gray-400' }
    default:
      return { label: status, classes: 'bg-gray-500/20 text-gray-400' }
  }
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `${mins}min atrás`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h atrás`
  return `${Math.floor(hours / 24)}d atrás`
}

interface VideoCardProps {
  job: JobSummary
  onEdit: (id: string) => void
}

export default function VideoCard({ job, onEdit }: VideoCardProps) {
  const canEdit = ['completed', 'editable'].includes(job.status)
  const badge = statusBadge(job.status)
  const gradient = STYLE_GRADIENTS[job.style] || 'from-gray-900/40 to-gray-800/40'
  const icon = STYLE_ICONS[job.style] || '🎬'

  return (
    <div className="rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden hover:border-[var(--border-hover)] transition group">
      {/* Thumbnail */}
      <div className={`aspect-video bg-gradient-to-br ${gradient} flex items-center justify-center`}>
        <span className="text-5xl opacity-15 group-hover:opacity-25 transition">{icon}</span>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="text-sm font-medium truncate text-gray-200" title={job.topic}>
          {job.topic}
        </h3>
        <div className="flex items-center gap-2 mt-2">
          <span className={`inline-flex items-center text-[10px] px-2 py-0.5 rounded-full font-medium ${badge.classes}`}>
            {badge.label}
          </span>
          <span className="text-[10px] text-gray-600">{job.duration_target}s</span>
          <span className="text-[10px] text-gray-600">{timeAgo(job.created_at)}</span>
        </div>
      </div>

      {/* Actions */}
      {(canEdit || job.download_url) && (
        <div className="px-4 pb-4 flex gap-2">
          {canEdit && (
            <button
              onClick={() => onEdit(job.job_id)}
              className="flex-1 py-2 rounded-lg bg-purple-600 text-white text-xs font-semibold hover:bg-purple-500 transition cursor-pointer"
            >
              {strings.dashboard.videos.edit}
            </button>
          )}
          {job.download_url && (
            <button
              type="button"
              onClick={() => downloadAuthenticatedFile(job.download_url!, `clipia-${job.job_id.slice(0, 8)}.mp4`)}
              className="flex-1 py-2 rounded-lg border border-[var(--border-default)] text-gray-400 text-xs font-medium text-center hover:border-gray-500 hover:text-gray-300 transition"
            >
              {strings.dashboard.videos.download}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
