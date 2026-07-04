'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Download, Loader2, Pencil, Share2, X } from 'lucide-react'
import { motion } from 'motion/react'
import { fetchAuthenticatedBlob, saveBlob } from '@/lib/download'
import { DURATIONS, EASE, useReducedMotionState } from '@/lib/motion'
import { useToast } from '@/components/ui/feedback'
import type { JobSummary } from '@/lib/editor-api'

interface VideoPlayerModalProps {
  job: JobSummary
  onClose: () => void
  onEdit?: (jobId: string) => void
}

/**
 * Player dedicado do vídeo final (acesso rápido a partir do card do dashboard).
 * O /download é Bearer-only — <video src> direto daria 401 — então buscamos o blob
 * autenticado UMA vez e ele alimenta player, download e compartilhamento sem re-fetch.
 */
export default function VideoPlayerModal({ job, onClose, onEdit }: VideoPlayerModalProps) {
  const reduceMotion = useReducedMotionState()
  const { success: toastSuccess, error: toastError } = useToast()
  const [src, setSrc] = useState<string | null>(null)
  const [loadProgress, setLoadProgress] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const blobRef = useRef<{ blob: Blob; filename: string | null } | null>(null)

  const fallbackFilename = `clipia-${job.job_id.slice(0, 8)}.mp4`
  const canEdit = onEdit && ['completed', 'editable'].includes(job.status)

  // Busca o blob autenticado com progresso; revoga o object URL ao desmontar.
  useEffect(() => {
    if (!job.download_url) return
    let cancelled = false
    let objectUrl: string | null = null
    setLoadError(null)
    setLoadProgress(0)
    fetchAuthenticatedBlob(job.download_url, (f) => { if (!cancelled) setLoadProgress(f) })
      .then((result) => {
        if (cancelled) return
        blobRef.current = result
        objectUrl = URL.createObjectURL(result.blob)
        setSrc(objectUrl)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : 'Não foi possível carregar o vídeo')
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [job.download_url, retryKey])

  // Esc fecha + trava o scroll do body enquanto o modal existe.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  const handleDownload = useCallback(() => {
    const cached = blobRef.current
    if (!cached) return
    saveBlob(cached.blob, cached.filename || fallbackFilename)
    toastSuccess('Download iniciado', 'Confira a pasta de downloads do navegador.')
  }, [fallbackFilename, toastSuccess])

  const handleShare = useCallback(async () => {
    const cached = blobRef.current
    if (!cached) return
    const file = new File([cached.blob], cached.filename || fallbackFilename, { type: 'video/mp4' })
    try {
      await navigator.share({ files: [file], title: job.topic })
    } catch (err) {
      // AbortError = usuário fechou o share sheet; não é erro.
      if (err instanceof DOMException && err.name === 'AbortError') return
      toastError('Não foi possível compartilhar', 'Baixe o vídeo e envie manualmente.')
    }
  }, [fallbackFilename, job.topic, toastError])

  const supportsShare =
    typeof navigator !== 'undefined' && typeof navigator.canShare === 'function' && typeof navigator.share === 'function'

  return createPortal(
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Assistir: ${job.topic}`}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: DURATIONS.fast, ease: EASE }}
        className="relative flex w-full max-w-sm flex-col overflow-hidden rounded-2xl border border-white/10 bg-[var(--bg-raised)] shadow-2xl"
      >
        {/* Cabeçalho */}
        <div className="flex items-start justify-between gap-3 border-b border-white/5 px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-bold text-white" title={job.topic}>{job.topic}</h2>
            <p className="text-[11px] text-slate-500">{job.duration_target}s · vídeo final</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar player"
            className="shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white"
          >
            <X size={16} />
          </button>
        </div>

        {/* Área do vídeo */}
        <div className="flex h-[min(62vh,560px)] items-center justify-center bg-black">
          {loadError ? (
            <div className="flex flex-col items-center gap-3 px-6 text-center">
              <p className="text-sm text-red-300">{loadError}</p>
              <button
                type="button"
                onClick={() => setRetryKey((k) => k + 1)}
                className="rounded-lg bg-coral px-4 py-2 text-xs font-semibold text-white transition hover:opacity-90"
              >
                Tentar novamente
              </button>
            </div>
          ) : src ? (
            <video src={src} controls autoPlay playsInline className="h-full w-full object-contain" />
          ) : (
            <div className="flex flex-col items-center gap-3 text-slate-400">
              <Loader2 size={22} className="animate-spin text-coral" />
              <p className="text-xs font-medium tabular-nums">
                {loadProgress > 0 ? `Carregando vídeo… ${Math.round(loadProgress * 100)}%` : 'Carregando vídeo…'}
              </p>
              <div className="h-1 w-40 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-coral to-azure transition-all duration-300"
                  style={{ width: `${Math.max(4, loadProgress * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Ações */}
        <div className="flex gap-2 border-t border-white/5 p-3">
          <button
            type="button"
            onClick={handleDownload}
            disabled={!src}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-coral py-2.5 text-sm font-bold text-white transition hover:opacity-90 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Download size={14} />
            Baixar
          </button>
          {supportsShare && (
            <button
              type="button"
              onClick={handleShare}
              disabled={!src}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/10 py-2.5 text-sm font-semibold text-white transition hover:bg-white/15 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Share2 size={14} />
              Compartilhar
            </button>
          )}
          {canEdit && (
            <button
              type="button"
              onClick={() => { onClose(); onEdit!(job.job_id) }}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/10 py-2.5 text-sm font-semibold text-white transition hover:bg-white/15 active:scale-[0.97]"
            >
              <Pencil size={14} />
              Editar
            </button>
          )}
        </div>
      </motion.div>
    </div>,
    document.body,
  )
}
