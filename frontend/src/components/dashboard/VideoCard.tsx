'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { strings } from '@/lib/strings';
import type { JobSummary } from '@/lib/editor-api'
import { downloadAuthenticatedFile, fetchAuthenticatedBlobUrl } from '@/lib/download'
import { GlowCard } from '@/components/ui/GlowCard'

const STYLE_GRADIENTS: Record<string, string> = {
  educational: 'from-coral/40 to-azure/40',
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
      return { label: strings.dashboard.generate.loading, classes: 'bg-coral/20 text-coral animate-pulse border border-coral/30' }
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

  // Preview do vídeo: /download é Bearer-only, então <video src> direto dava 401 (BUG-R002).
  // Carrega como blob autenticado no mount (para aparecer sempre) e revoga no unmount.
  const [previewSrc, setPreviewSrc] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hoveringRef = useRef(false)

  useEffect(() => {
    return () => { if (previewSrc) URL.revokeObjectURL(previewSrc) }
  }, [previewSrc])

  useEffect(() => {
    if (!job.download_url) return
    fetchAuthenticatedBlobUrl(job.download_url)
      .then(url => setPreviewSrc(url))
      .catch(() => {})
  }, [job.download_url])

  const handleEnter = useCallback(() => {
    hoveringRef.current = true
    if (previewSrc) videoRef.current?.play().catch(() => {})
  }, [previewSrc])

  const handleLeave = useCallback(() => {
    hoveringRef.current = false
    const v = videoRef.current
    if (v) { v.pause(); v.currentTime = 0 }
  }, [])

  return (
    <GlowCard intensity={0.2} className="h-full">
      <div className="flex flex-col h-full bg-[#110d1a] hover:bg-[#161122] transition-colors rounded-xl overflow-hidden relative">
        {/* Thumbnail - shorter on mobile, taller on desktop */}
        <div
          className={`w-full aspect-[3/4] sm:aspect-[9/16] bg-gradient-to-br ${gradient} flex flex-col items-center justify-center relative overflow-hidden group`}
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
        >
          <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 mix-blend-overlay"></div>

          {job.download_url && previewSrc && (
            <video
              ref={videoRef}
              src={previewSrc}
              className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity duration-500"
              muted
              loop
              playsInline
              onLoadedData={() => { if (hoveringRef.current) videoRef.current?.play().catch(() => {}) }}
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
        <div className="p-4 flex-1 flex flex-col border-t border-white/5">
          <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug mb-3 flex-1" title={job.topic}>
            {job.topic}
          </h3>

          <div className="flex items-center gap-3 text-xs text-slate-400 font-medium mb-3">
            <span className="flex items-center gap-1">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
              {job.duration_target}s
            </span>
            <span>&bull;</span>
            <span>{timeAgo(job.created_at)}</span>
          </div>

          {/* Always-visible action buttons */}
          {(canEdit || job.download_url) && (
            <div className="flex gap-2 mt-auto">
              {canEdit && (
                <button
                  onClick={() => onEdit(job.job_id)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-3 sm:py-2.5 rounded-lg bg-coral text-white text-sm font-bold hover:bg-coral active:scale-[0.97] transition"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  {strings.dashboard.videos.edit}
                </button>
              )}
              {job.download_url && (
                <button
                  type="button"
                  onClick={() => downloadAuthenticatedFile(job.download_url!, `clipia-${job.job_id.slice(0, 8)}.mp4`)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-3 sm:py-2.5 rounded-lg bg-white/10 border border-white/10 text-white text-sm font-semibold hover:bg-white/15 active:scale-[0.97] transition"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  {strings.dashboard.videos.download}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </GlowCard>
  )
}
