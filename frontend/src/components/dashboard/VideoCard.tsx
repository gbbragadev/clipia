'use client'

import { strings } from '@/lib/strings';
import type { JobSummary } from '@/lib/editor-api'
import { downloadAuthenticatedFile } from '@/lib/download'
import { GlowCard } from '@/components/ui/GlowCard'

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
      return { label: 'Pronto', classes: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' }
    case 'failed':
    case 'error':
      return { label: 'Erro', classes: 'bg-red-500/20 text-red-400 border border-red-500/30' }
    case 'processing':
      return { label: strings.dashboard.generate.loading, classes: 'bg-purple-500/20 text-purple-400 animate-pulse border border-purple-500/30' }
    case 'queued':
      return { label: 'Na fila', classes: 'bg-gray-500/20 text-gray-400 border border-gray-500/30' }
    default:
      return { label: status, classes: 'bg-gray-500/20 text-gray-400 border border-gray-500/30' }
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
    <GlowCard intensity={0.2} className="h-full">
      <div className="flex flex-col h-full bg-[#110d1a] hover:bg-[#161122] transition-colors rounded-xl overflow-hidden relative">
        {/* Thumbnail - Changed to 9:16 aspect ratio */}
        <div className={`w-full aspect-[9/16] bg-gradient-to-br ${gradient} flex flex-col items-center justify-center relative overflow-hidden group`}>
          <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 mix-blend-overlay"></div>
          
          {job.download_url && (
            <video
              src={job.download_url}
              className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity duration-500"
              muted
              loop
              onMouseEnter={(e) => e.currentTarget.play()}
              onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
            />
          )}

          {!job.download_url && (
            <span className="text-6xl opacity-30 group-hover:opacity-50 group-hover:scale-110 transition-all duration-500 z-10">{icon}</span>
          )}

          {/* Top Info Overlay */}
          <div className="absolute top-0 left-0 w-full p-3 bg-gradient-to-b from-black/80 to-transparent flex justify-between items-start z-10">
            <span className={`inline-flex items-center text-[10px] px-2.5 py-1 rounded-full font-semibold uppercase tracking-wider backdrop-blur-sm ${badge.classes}`}>
              {badge.label}
            </span>
          </div>

          {/* Play Overlay Hint */}
          {job.download_url && (
            <div className="absolute inset-0 flex items-center justify-center z-10 opacity-0 group-hover:opacity-100 transition-opacity">
               <div className="w-12 h-12 rounded-full bg-black/50 backdrop-blur-md flex items-center justify-center border border-white/20">
                 <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                   <polygon points="5 3 19 12 5 21 5 3" />
                 </svg>
               </div>
            </div>
          )}
        </div>

        {/* Content Footer */}
        <div className="p-5 flex-1 flex flex-col border-t border-white/5">
          <h3 className="text-base font-bold text-white line-clamp-2 leading-snug mb-3 flex-1" title={job.topic}>
            {job.topic}
          </h3>
          
          <div className="flex items-center justify-between mt-auto pt-4 border-t border-white/5">
            <div className="flex items-center gap-3 text-xs text-slate-400 font-medium">
              <span className="flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                {job.duration_target}s
              </span>
              <span>&bull;</span>
              <span>{timeAgo(job.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Floating Actions */}
        {(canEdit || job.download_url) && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col gap-2 w-[80%] z-20">
            {canEdit && (
              <button
                onClick={() => onEdit(job.job_id)}
                className="w-full py-2.5 rounded-xl bg-purple-600/90 backdrop-blur-md text-white text-sm font-bold hover:bg-purple-500 transition shadow-xl border border-purple-400/30"
              >
                {strings.dashboard.videos.edit}
              </button>
            )}
            {job.download_url && (
              <button
                type="button"
                onClick={() => downloadAuthenticatedFile(job.download_url!, `clipia-${job.job_id.slice(0, 8)}.mp4`)}
                className="w-full py-2.5 rounded-xl bg-black/60 backdrop-blur-md border border-white/20 text-white text-sm font-semibold text-center hover:bg-white/10 transition shadow-xl"
              >
                {strings.dashboard.videos.download}
              </button>
            )}
          </div>
        )}
      </div>
    </GlowCard>
  )
}
