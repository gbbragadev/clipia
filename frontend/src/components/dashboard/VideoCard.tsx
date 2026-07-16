'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { AnimatePresence } from 'motion/react'
import { Check, Copy, Link2Off, Loader2, Play, Share2 } from 'lucide-react'
import { strings } from '@/lib/strings';
import { ACTIVE_JOB_STATUSES, STEP_LABELS, type JobSummary } from '@/lib/editor-api'
import { downloadAuthenticatedFile, fetchAuthenticatedBlobUrl } from '@/lib/download'
import { canManagePublicShare, createPublicShare, revokePublicShare, type PublicShareCreated } from '@/lib/public-shares'
import { GlowCard } from '@/components/ui/GlowCard'
import { StatusBadge, jobStatusBadge } from '@/components/ui/StatusBadge'
import { useToast } from '@/components/ui/feedback'
import VideoPlayerModal from './VideoPlayerModal'
import JobStepper from './JobStepper'

const STYLE_GRADIENTS: Record<string, string> = {
  educational: 'from-coral/40 to-azure/40',
  storytelling: 'from-azure/30 to-coral/20',
  news: 'from-slate-800/40 to-gray-900/40',
  comedy: 'from-rose-900/40 to-amber-900/40',
}

const STYLE_ICONS: Record<string, string> = {
  educational: '📚',
  storytelling: '📖',
  news: '📰',
  comedy: '😂',
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
  onCancel?: (id: string) => void
}

export default function VideoCard({ job, onEdit, onCancel }: VideoCardProps) {
  const { success: toastSuccess, error: toastError } = useToast()
  const canEdit = ['completed', 'editable'].includes(job.status)
  // Delight one-shot: acende um anel coral quando ESTE card transiciona de "gerando"
  // para "pronto" durante a sessão (nunca em cards que já montaram prontos).
  const prevStatusRef = useRef(job.status)
  const [justCompleted, setJustCompleted] = useState(false)
  useEffect(() => {
    const prev = prevStatusRef.current
    prevStatusRef.current = job.status
    if (
      ACTIVE_JOB_STATUSES.includes(prev) &&
      ['completed', 'editable'].includes(job.status)
    ) {
      setJustCompleted(true)
      const t = setTimeout(() => setJustCompleted(false), 1000)
      return () => clearTimeout(t)
    }
  }, [job.status])
  const canCancel = onCancel ? ['processing', 'queued'].includes(job.status) : false
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [showPlayer, setShowPlayer] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [dlProgress, setDlProgress] = useState<number | null>(null)
  const [publicShare, setPublicShare] = useState<PublicShareCreated | null>(null)
  const [sharing, setSharing] = useState(false)
  const [shareCopied, setShareCopied] = useState(false)
  const badge = jobStatusBadge(job.status)
  const gradient = STYLE_GRADIENTS[job.style] || 'from-gray-900/40 to-gray-800/40'
  const icon = STYLE_ICONS[job.style] || '🎬'

  // Poster real do vídeo (JPEG ~30KB via rota autenticada — barato o bastante p/ carregar
  // no mount, ao contrário do preview MP4 que segue lazy no hover).
  const [thumbSrc, setThumbSrc] = useState<string | null>(null)
  useEffect(() => {
    if (!job.thumbnail_url) return
    let revoked: string | null = null
    fetchAuthenticatedBlobUrl(job.thumbnail_url)
      .then((url) => {
        revoked = url
        setThumbSrc(url)
      })
      .catch(() => {})
    return () => {
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [job.thumbnail_url])

  // Preview do vídeo: /download é Bearer-only, então <video src> direto dava 401 (BUG-R002).
  // LAZY (perf): antes o blob autenticado era baixado no mount de TODOS os cards, o que
  // puxava o MP4 inteiro de cada item só para mostrar o preview. Agora só buscamos o blob
  // quando o usuário hover no card (preview sob demanda) — em mobile/4G isso evita N downloads
  // pesados de uma vez. O blob fica em cache enquanto o card existe, então re-hover é instantâneo.
  const [previewSrc, setPreviewSrc] = useState<string | null>(null)
  const [previewRequested, setPreviewRequested] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hoveringRef = useRef(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    return () => { if (previewSrc) URL.revokeObjectURL(previewSrc) }
  }, [previewSrc])

  const handleEnter = useCallback(() => {
    hoveringRef.current = true
    // Só dispara o download do MP4 no primeiro hover (lazy preview).
    if (job.download_url && !previewRequested) {
      setPreviewRequested(true)
      fetchAuthenticatedBlobUrl(job.download_url)
        .then((url) => {
          // Card desmontou durante o fetch (filtro/re-fetch da grid): revoga na hora,
          // senão o setState vira no-op e o blob do MP4 inteiro vaza até a navegação.
          if (!mountedRef.current) {
            URL.revokeObjectURL(url)
            return
          }
          setPreviewSrc(url)
        })
        .catch(() => {})
      return
    }
    if (previewSrc) videoRef.current?.play().catch(() => {})
  }, [job.download_url, previewRequested, previewSrc])

  const handleLeave = useCallback(() => {
    hoveringRef.current = false
    const v = videoRef.current
    if (v) { v.pause(); v.currentTime = 0 }
  }, [])

  // Download com feedback real: spinner + % (stream) e toast de sucesso/erro.
  // Antes a Promise rejeitada era engolida — o botão parecia morto em 4G (bug reportado).
  const handleDownload = useCallback(async () => {
    if (!job.download_url || downloading) return
    setDownloading(true)
    setDlProgress(null)
    try {
      await downloadAuthenticatedFile(job.download_url, `clipia-${job.job_id.slice(0, 8)}.mp4`, setDlProgress)
      toastSuccess('Download concluído', 'Confira a pasta de downloads do navegador.')
    } catch (err) {
      toastError('Falha no download', err instanceof Error ? err.message : 'Tente novamente em instantes.')
    } finally {
      setDownloading(false)
      setDlProgress(null)
    }
  }, [job.download_url, job.job_id, downloading, toastSuccess, toastError])

  const handlePublishShare = useCallback(async () => {
    if (sharing) return
    setSharing(true)
    try {
      const created = await createPublicShare(job.job_id)
      setPublicShare(created)
      toastSuccess('Link público criado', 'O vídeo agora pode ser visto por quem receber este link.')
    } catch (err) {
      toastError('Falha ao publicar', err instanceof Error ? err.message : 'Tente novamente em instantes.')
    } finally {
      setSharing(false)
    }
  }, [job.job_id, sharing, toastError, toastSuccess])

  const handleCopyShare = useCallback(async () => {
    if (!publicShare) return
    try {
      await navigator.clipboard.writeText(publicShare.url)
      setShareCopied(true)
      window.setTimeout(() => setShareCopied(false), 2000)
    } catch {
      toastError('Não foi possível copiar', 'Selecione o link e copie manualmente.')
    }
  }, [publicShare, toastError])

  const handleRevokeShare = useCallback(async () => {
    if (!publicShare || sharing) return
    setSharing(true)
    try {
      await revokePublicShare(job.job_id)
      setPublicShare(null)
      setShareCopied(false)
      toastSuccess('Link revogado', 'O vídeo deixou de estar disponível nesse endereço.')
    } catch (err) {
      toastError('Falha ao revogar', err instanceof Error ? err.message : 'Tente novamente em instantes.')
    } finally {
      setSharing(false)
    }
  }, [job.job_id, publicShare, sharing, toastError, toastSuccess])

  return (
    <GlowCard intensity={0.2} className="h-full">
      <div className={`flex flex-col h-full bg-[var(--bg-raised)] hover:bg-[var(--bg-surface)] transition-colors rounded-xl overflow-hidden relative ${justCompleted ? 'anim-ready-ring' : ''}`}>
        {/* Thumbnail - shorter on mobile, taller on desktop */}
        <div
          className={`w-full aspect-[3/4] sm:aspect-[9/16] bg-gradient-to-br ${gradient} flex flex-col items-center justify-center relative overflow-hidden group ${job.download_url ? 'cursor-pointer' : ''}`}
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
          onClick={() => { if (job.download_url) setShowPlayer(true) }}
        >
          <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 mix-blend-overlay"></div>

          {/* Poster do vídeo real (o preview MP4 no hover renderiza por cima) */}
          {thumbSrc && (
            <img
              src={thumbSrc}
              alt=""
              aria-hidden
              className="absolute inset-0 h-full w-full object-cover"
            />
          )}

          {job.download_url && previewSrc && (
            // autoPlay (muted = sempre permitido) resolve o PRIMEIRO hover: quando o blob
            // chega e o <video> monta, o ref ainda era null no .then — play() manual era no-op.
            <video
              ref={videoRef}
              src={previewSrc}
              className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity duration-500"
              muted
              loop
              playsInline
              autoPlay
              onLoadedData={() => { if (!hoveringRef.current) { videoRef.current?.pause(); if (videoRef.current) videoRef.current.currentTime = 0 } }}
            />
          )}

          {!job.download_url && !thumbSrc && (
            <span className="text-6xl opacity-30 group-hover:opacity-50 group-hover:scale-110 transition-[transform,opacity] duration-200 z-10">{icon}</span>
          )}

          {/* Top Info Overlay */}
          <div className="absolute top-0 left-0 w-full p-3 bg-gradient-to-b from-black/80 to-transparent flex flex-wrap justify-between items-start gap-1 z-10">
            <StatusBadge variant={badge.variant} className="shrink-0 backdrop-blur-sm">
              {badge.label}
            </StatusBadge>
            {job.degraded && (
              <span
                className="inline-flex shrink-0 items-center gap-1 text-[10px] px-2.5 py-1 rounded-full font-semibold backdrop-blur-sm bg-amber-500/20 text-amber-300 border border-amber-500/30"
                title="O provedor principal de roteiro estava indisponível — este vídeo usou o modo econômico. Regenere mais tarde para qualidade total."
              >
                ⚠ Qualidade reduzida
              </span>
            )}
          </div>

          {/* Abre o player dedicado (não é mais só decoração) */}
          {job.download_url && (
            <button
              type="button"
              aria-label={`Assistir "${job.topic}"`}
              onClick={(e) => { e.stopPropagation(); setShowPlayer(true) }}
              className="absolute inset-0 flex items-center justify-center z-10 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity cursor-pointer"
            >
              <span className="w-12 h-12 rounded-full bg-black/50 backdrop-blur-md flex items-center justify-center border border-white/20 transition-transform group-hover:scale-105">
                <Play size={20} className="fill-white text-white" />
              </span>
            </button>
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
            <span title={job.created_at ? new Date(job.created_at).toLocaleString('pt-BR') : undefined}>
              {timeAgo(job.created_at)}
            </span>
          </div>

          {/* Progresso em tempo real (a grid faz polling enquanto o job está ativo):
              stepper de macro-etapas + etapa fina + % honesto + posição real na fila */}
          {ACTIVE_JOB_STATUSES.includes(job.status) && (
            <div className="mb-3 space-y-1.5">
              {job.status === 'queued' && job.queue_position != null && (
                <p className="text-[11px] font-medium text-azure">
                  {job.queue_position === 0
                    ? 'Você é o próximo — começa em instantes'
                    : `Na fila — ${job.queue_position} à frente`}
                </p>
              )}
              <JobStepper step={job.current_step} queued={job.status === 'queued'} />
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-coral">
                  {STEP_LABELS[job.current_step ?? ''] || (job.status === 'queued' ? 'Aguardando o estúdio...' : 'Processando...')}
                </span>
                <span className="text-[11px] text-slate-500 tabular-nums">
                  {Math.round((job.progress ?? 0) * 100)}%
                </span>
              </div>
              <div className="h-1 rounded-full overflow-hidden bg-white/10">
                <div
                  className="h-full w-full origin-left rounded-full bg-gradient-to-r from-coral to-azure transition-transform duration-500 ease-out"
                  style={{ transform: `scaleX(${Math.max(0.04, job.progress ?? 0)})` }}
                />
              </div>
            </div>
          )}

          {/* Always-visible action buttons */}
          {(canEdit || job.download_url || canCancel) && (
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
                  onClick={handleDownload}
                  disabled={downloading}
                  className="flex-1 flex items-center justify-center gap-1.5 py-3 sm:py-2.5 rounded-lg bg-white/10 border border-white/10 text-white text-sm font-semibold hover:bg-white/15 active:scale-[0.97] transition disabled:cursor-wait disabled:opacity-70"
                >
                  {downloading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span className="tabular-nums">{dlProgress != null ? `${Math.round(dlProgress * 100)}%` : 'Baixando…'}</span>
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                      {strings.dashboard.videos.download}
                    </>
                  )}
                </button>
              )}
              {canCancel && (
                <button
                  type="button"
                  aria-label={`Cancelar a geração de "${job.topic}"`}
                  onClick={() => setConfirmCancel(true)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-3 sm:py-2.5 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm font-semibold hover:bg-danger/20 active:scale-[0.97] transition"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
                  Cancelar
                </button>
              )}
            </div>
          )}

          {/* Confirmação de cancelamento */}
          {canManagePublicShare(job) && (
            <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.035] p-3">
              <p className="text-[11px] leading-relaxed text-slate-400">
                Só fica público quando você publicar. Quem tiver o link poderá assistir até você revogá-lo.
              </p>
              {publicShare ? (
                <>
                  <input
                    readOnly
                    value={publicShare.url}
                    aria-label="Link público do vídeo"
                    className="mt-2 w-full truncate rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-[11px] text-slate-300"
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={handleCopyShare}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-azure/15 px-2 py-2 text-xs font-semibold text-azure hover:bg-azure/25 transition"
                    >
                      {shareCopied ? <Check size={13} /> : <Copy size={13} />}
                      {shareCopied ? 'Link copiado' : 'Copiar link'}
                    </button>
                    <button
                      type="button"
                      onClick={handleRevokeShare}
                      disabled={sharing}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-red-500/25 bg-red-500/10 px-2 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/20 disabled:opacity-60 transition"
                    >
                      {sharing ? <Loader2 size={13} className="animate-spin" /> : <Link2Off size={13} />}
                      Revogar link
                    </button>
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  onClick={handlePublishShare}
                  disabled={sharing}
                  className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-xs font-semibold text-white hover:bg-white/15 disabled:opacity-60 transition"
                >
                  {sharing ? <Loader2 size={13} className="animate-spin" /> : <Share2 size={13} />}
                  {sharing ? 'Publicando…' : 'Publicar link'}
                </button>
              )}
            </div>
          )}

          {confirmCancel && canCancel && (
            <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3">
              <p className="text-xs text-red-200/80 mb-2">
                Cancelar este vídeo? O crédito da geração será devolvido.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setConfirmCancel(false); onCancel!(job.job_id) }}
                  className="flex-1 py-2 rounded-md bg-red-500 text-white text-xs font-semibold hover:bg-red-600 transition"
                >
                  Sim, cancelar
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmCancel(false)}
                  className="flex-1 py-2 rounded-md bg-white/5 border border-white/10 text-white/70 text-xs font-medium hover:bg-white/10 transition"
                >
                  Manter
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Player dedicado (portal — escapa do overflow/transform do card) */}
      <AnimatePresence>
        {showPlayer && (
          <VideoPlayerModal job={job} onClose={() => setShowPlayer(false)} onEdit={onEdit} />
        )}
      </AnimatePresence>
    </GlowCard>
  )
}
