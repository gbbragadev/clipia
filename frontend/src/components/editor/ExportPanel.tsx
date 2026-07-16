'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, Clapperboard, Download, Loader2, RotateCcw, X } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { motion } from 'motion/react'
import { useEditor } from '@/contexts/EditorContext'
import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'
import { useAuth } from '@/contexts/AuthContext'
import { downloadAuthenticatedFile } from '@/lib/download'
import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'
import { useToast } from '@/components/ui/feedback'
import ExportCostBanner from '@/components/dashboard/ExportCostBanner'
import { STEP_LABELS } from '@/lib/editor-api'
import { formatRenderElapsed } from '@/lib/editor-render-revision'
import { trackBackgroundRender } from '@/lib/render-background'

/**
 * Estado do re-render (a fonte da verdade é o Redis via /status):
 * - idle: nenhum render disparado (narração stale aguardando decisão do usuário)
 * - rendering: worker aplicando as edições — download BLOQUEADO (antes o botão
 *   ficava ativo e baixava a versão pré-edição: bug reportado pelo fundador)
 * - ready: arquivo final reflete as edições
 * - error: render falhou — pode baixar a versão anterior explicitamente
 */
type RenderState = 'idle' | 'rendering' | 'ready' | 'error'

interface PlatformCaption {
  platform: string
  icon: string
  maxChars: number | null
  caption: string
}

export function ExportPanel({ onClose }: { onClose: () => void }) {
  const {
    composition,
    jobId,
    narrationStale,
    setActivePanel,
    hasUnrenderedChanges,
    prepareRender,
    completeRender,
    clearRenderTracking,
    restoreRevision,
  } = useEditor()
  const router = useRouter()
  const { user } = useAuth()
  const { success: toastSuccess, error: toastError } = useToast()
  const reduceMotion = useReducedMotionState()

  const [renderState, setRenderState] = useState<RenderState>(() => (
    composition?.renderingRevision != null
      ? 'rendering'
      : hasUnrenderedChanges ? 'idle' : 'ready'
  ))
  const [renderProgress, setRenderProgress] = useState(hasUnrenderedChanges ? 0 : 1)
  const [renderDetail, setRenderDetail] = useState<string | null>(null)
  const [renderStep, setRenderStep] = useState<string | null>(null)
  const [nowMs, setNowMs] = useState(Date.now)
  // Custo fresco vindo do /status (mount + polls). O valor da composition é o snapshot
  // do load do editor — ai-suggest (0,5/consulta) e render/reset mudam no servidor e o
  // banner mentia (backlog 11/07). Fallback: snapshot da composition.
  const [pendingCredits, setPendingCredits] = useState<number>(composition?.pendingCredits ?? 0)
  const [error, setError] = useState<string | null>(null)
  const [staleAccepted, setStaleAccepted] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [dlProgress, setDlProgress] = useState<number | null>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [revisionDownloading, setRevisionDownloading] = useState<number | null>(null)
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null)

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)
  const openerRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    unmounted.current = false
    return () => {
      unmounted.current = true
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [])

  useEffect(() => {
    if (renderState !== 'rendering') return
    setNowMs(Date.now())
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [renderState])

  const generateCaptions = useCallback((): PlatformCaption[] => {
    const title = composition?.title || 'Meu vídeo'
    const hashtags = '#shorts #clipia #viral'
    return [
      { platform: 'YouTube Shorts', icon: 'YT', maxChars: null, caption: `${title}\n\n${hashtags}` },
      { platform: 'TikTok', icon: 'TT', maxChars: 150, caption: `${title} ${hashtags}`.slice(0, 150) },
      { platform: 'Instagram Reels', icon: 'IG', maxChars: null, caption: `${title}\n\n${hashtags}` },
    ]
  }, [composition])

  const [captions, setCaptions] = useState<PlatformCaption[]>(generateCaptions)

  const updateCaption = (index: number, text: string) => {
    setCaptions((prev) => {
      const next = [...prev]
      const maxChars = next[index].maxChars
      next[index] = { ...next[index], caption: maxChars ? text.slice(0, maxChars) : text }
      return next
    })
  }

  const copyToClipboard = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch { /* fallback */ }
  }

  const authHeaders = useCallback((): Record<string, string> => {
    const token = getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [])

  // Poll do /status até o worker terminar. O backend marca "rendering" no Redis
  // ANTES de enfileirar, então "completed" aqui significa re-render concluído de
  // verdade (não o "completed" estale do pipeline original).
  const pollStatus = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/status`, { headers: authHeaders() })
      if (!res.ok) throw new Error(await readApiError(res, 'Erro ao verificar status'))
      const data = await res.json()
      if (unmounted.current) return
      if (typeof data.pending_credits === 'number') setPendingCredits(data.pending_credits)
      setRenderStep(typeof data.current_step === 'string' ? data.current_step : null)

      if (data.status === 'completed') {
        await completeRender()
        if (unmounted.current) return
        setRenderState('ready')
        setRenderProgress(1)
        setRenderDetail(null)
        toastSuccess('Vídeo atualizado', 'Suas edições foram aplicadas ao arquivo final.')
      } else if (data.status === 'error') {
        await clearRenderTracking()
        if (unmounted.current) return
        setRenderState('error')
        setError(data.error || 'Erro na renderização')
      } else {
        setRenderProgress(Number(data.progress) || 0)
        setRenderDetail(typeof data.detail === 'string' && data.detail ? data.detail : null)
        pollTimer.current = setTimeout(pollStatus, 2500)
      }
    } catch (pollErr) {
      if (unmounted.current) return
      setRenderState('error')
      setError(pollErr instanceof Error ? pollErr.message : 'Erro ao verificar status')
    }
  }, [jobId, authHeaders, toastSuccess, completeRender, clearRenderTracking])

  const handleRender = useCallback(async () => {
    setError(null)
    setRenderState('rendering')
    setRenderProgress(0)
    setRenderDetail(null)
    setRenderStep('queued')
    setNowMs(Date.now())
    // O render lê o que está no DISCO: sem flush, editar e exportar em <1,5s (debounce do
    // auto-save) renderizava estado velho — e DEBITAVA créditos por ele (achado R1 12/07).
    const saved = await prepareRender(user?.name || user?.email || 'Você')
    if (!saved) {
      if (unmounted.current) return
      setRenderState('error')
      setError('Suas edições não foram salvas (falha de conexão). Tente novamente antes de renderizar.')
      return
    }
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/render`, { method: 'POST', headers: authHeaders() })
      if (!res.ok) throw new Error(await readApiError(res, `Erro ${res.status}`))
      trackBackgroundRender({
        jobId,
        revision: composition?.editRevision ?? 0,
        topic: composition?.title || 'Vídeo ClipIA',
        startedAt: new Date().toISOString(),
      })
      pollTimer.current = setTimeout(pollStatus, 2000)
    } catch (err) {
      if (unmounted.current) return
      await clearRenderTracking()
      setRenderState('error')
      setError(err instanceof Error ? err.message : 'Erro ao renderizar')
    }
  }, [jobId, authHeaders, pollStatus, prepareRender, clearRenderTracking, user, composition])

  // O render NÃO dispara mais ao abrir o modal: um toque acidental em "Exportar"
  // (alvo pequeno no mobile) enfileirava ~2 min de render e debitava pending_credits
  // sem confirmação. Agora o usuário confirma no botão "Aplicar edições".
  // Foco entra no modal, fica contido e volta ao acionador ao fechar.
  useEffect(() => {
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab' || !panelRef.current) return
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )).filter((element) => element.offsetParent !== null)
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(focusTimer)
      window.removeEventListener('keydown', onKey)
      openerRef.current?.focus()
    }
  }, [onClose])

  // Render em curso ao ABRIR (disparado antes, modal fechado e reaberto): retoma o
  // acompanhamento em vez de oferecer "Aplicar edições" por cima do render vivo
  // (achado do audit 11/07 — o botão ficava ativo durante o render).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${jobId}/status`, { headers: authHeaders() })
        if (!res.ok || cancelled || unmounted.current) return
        const data = await res.json()
        if (typeof data.pending_credits === 'number') setPendingCredits(data.pending_credits)
        setRenderStep(typeof data.current_step === 'string' ? data.current_step : null)
        if (data.status === 'rendering') {
          setRenderState('rendering')
          setRenderProgress(Number(data.progress) || 0)
          setRenderDetail(typeof data.detail === 'string' && data.detail ? data.detail : null)
          pollTimer.current = setTimeout(pollStatus, 2500)
        } else if (data.status === 'completed' && composition?.renderingRevision != null) {
          await completeRender()
          if (cancelled || unmounted.current) return
          setRenderState('ready')
          setRenderProgress(1)
        } else if (data.status === 'completed') {
          setRenderState(hasUnrenderedChanges ? 'idle' : 'ready')
          setRenderProgress(hasUnrenderedChanges ? 0 : 1)
        } else if (data.status === 'error') {
          await clearRenderTracking()
          if (cancelled || unmounted.current) return
          setRenderState('error')
          setError(data.error || 'Erro na renderização')
        }
      } catch { /* sem status → modal abre normal no estado idle */ }
    })()
    return () => { cancelled = true }
    // Só na montagem: pollStatus/authHeaders são estáveis o suficiente aqui.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDownload = useCallback(async () => {
    if (downloading || renderState === 'rendering') return
    setDownloading(true)
    setDlProgress(null)
    try {
      await downloadAuthenticatedFile(`/api/v1/jobs/${jobId}/download`, `clipia-${jobId.slice(0, 8)}.mp4`, setDlProgress)
      toastSuccess('Download concluído', 'Confira a pasta de downloads do navegador.')
    } catch (err) {
      toastError('Falha no download', err instanceof Error ? err.message : 'Tente novamente em instantes.')
    } finally {
      setDownloading(false)
      setDlProgress(null)
    }
  }, [jobId, downloading, renderState, toastSuccess, toastError])

  const handleRevisionDownload = useCallback(async (revision: number) => {
    if (revisionDownloading !== null || renderState === 'rendering') return
    setRevisionDownloading(revision)
    try {
      const isCurrent = revision === composition?.renderedRevision
      const url = isCurrent
        ? `/api/v1/jobs/${jobId}/download`
        : `/api/v1/jobs/${jobId}/revisions/${revision}/download`
      await downloadAuthenticatedFile(url, `clipia-${jobId.slice(0, 8)}-revision-${revision}.mp4`)
      toastSuccess('Revisão baixada', `O arquivo da revisão ${revision} foi salvo.`)
    } catch (err) {
      toastError('Falha no download', err instanceof Error ? err.message : 'Tente novamente em instantes.')
    } finally {
      setRevisionDownloading(null)
    }
  }, [revisionDownloading, renderState, composition?.renderedRevision, jobId, toastSuccess, toastError])

  const handleRestoreRevision = useCallback((revision: number) => {
    if (!restoreRevision(revision)) return
    const message = `Ajustes da revisão ${revision} restaurados. Regere a narração se necessário e renderize para aplicar.`
    setRestoreMessage(message)
    setRenderState('ready')
    toastSuccess(`Revisão ${revision} restaurada`, 'Os ajustes foram carregados como uma nova edição.')
  }, [restoreRevision, toastSuccess])

  const handleContinueDashboard = useCallback(() => {
    trackBackgroundRender({
      jobId,
      revision: composition?.renderingRevision ?? composition?.editRevision ?? 0,
      topic: composition?.title || 'Vídeo ClipIA',
      startedAt: composition?.renderStartedAt ?? new Date().toISOString(),
    })
    router.push('/dashboard')
  }, [composition, jobId, router])

  const downloadIsPrevious = hasUnrenderedChanges
  const renderPercent = Math.round(Math.min(1, Math.max(0, renderProgress)) * 100)
  const showRenderCta = hasUnrenderedChanges && (renderState === 'idle' || renderState === 'ready')
  const renderStageLabel = renderStep ? STEP_LABELS[renderStep] ?? renderDetail ?? 'Processando edição...' : 'Preparando edição...'
  const renderElapsed = formatRenderElapsed(composition?.renderStartedAt ?? null, nowMs)
  const activeRevision = composition?.renderingRevision ?? composition?.renderedRevision ?? 0
  const activeReceipt = [...(composition?.revisionHistory ?? [])]
    .reverse()
    .find((entry) => entry.revision === activeRevision)
  const completedHistory = [...(composition?.revisionHistory ?? [])]
    .filter((entry) => entry.status === 'completed')
    .reverse()
  const renderedAtTime = composition?.renderedAt ? Date.parse(composition.renderedAt) : Number.NaN
  const renderedWhen = Number.isFinite(renderedAtTime)
    ? Date.now() - renderedAtTime < 60_000
      ? 'Renderizado agora'
      : `renderizada em ${new Intl.DateTimeFormat('pt-BR', {
        dateStyle: 'short',
        timeStyle: 'short',
      }).format(renderedAtTime)}`
    : 'arquivo atual'

  return (
    <motion.div
      className="export-overlay"
      initial={reduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: DURATIONS.fast, ease: EASE }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        ref={panelRef}
        className="export-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-panel-title"
        initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: DURATIONS.fast, ease: EASE }}
      >
        <button ref={closeButtonRef} type="button" className="export-panel__close" onClick={onClose} aria-label="Fechar">
          <X size={16} />
        </button>

        <h2 id="export-panel-title" className="export-panel__title">Exportar vídeo</h2>

        {narrationStale && !staleAccepted && (
          <div className="export-stale">
            O texto ou a ordem das cenas mudou desde a última narração. Se exportar agora, o áudio e as
            legendas NÃO vão refletir o novo texto ou a nova sequência.
            <div className="export-stale__actions">
              <button
                type="button"
                className="export-stale__btn"
                onClick={() => { setActivePanel('voice'); onClose() }}
              >
                Regenerar narração primeiro
              </button>
              <button
                type="button"
                className="export-stale__btn export-stale__btn--ghost"
                onClick={() => { setStaleAccepted(true); handleRender() }}
              >
                Exportar mesmo assim
              </button>
            </div>
          </div>
        )}

        {pendingCredits > 0 && (
          <div style={{ marginBottom: 12 }}>
            <ExportCostBanner
              pendingCredits={pendingCredits}
              userCredits={user?.credits ?? 0}
            />
          </div>
        )}
        {hasUnrenderedChanges && pendingCredits <= 0 && (
          <p className="export-cost-free">Grátis — seu saldo não será alterado.</p>
        )}

        {/* Confirmação explícita: custo conhecido sem prometer duração ainda não calibrada. */}
        {showRenderCta && !(narrationStale && !staleAccepted) && (
          <button type="button" className="export-download" onClick={handleRender}>
            <Clapperboard size={16} />
            Aplicar edições e renderizar
            {pendingCredits > 0 && ` · ${pendingCredits} créd.`}
          </button>
        )}

        {/* Status do render */}
        {renderState === 'rendering' && (
          <div className="export-status export-status--rendering" role="status" aria-live="polite">
            <Loader2 size={14} className="export-status__spinner" />
            <div className="export-status__body">
              <div className="export-progress__label">
                <span>{renderDetail || 'Aplicando suas edições…'}</span>
                <strong>{renderPercent}%</strong>
              </div>
              <div className="export-render-meta">
                <span>Etapa · {renderStageLabel}</span>
                <span>Tempo decorrido · {renderElapsed}</span>
              </div>
              <div
                className="export-progress"
                role="progressbar"
                aria-label="Progresso da renderização"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={renderPercent}
                aria-valuetext={`${renderPercent}%, ${renderStageLabel}, ${renderElapsed} decorridos`}
              >
                <div className="export-progress__fill" style={{ transform: `scaleX(${Math.max(0.06, renderProgress)})` }} />
              </div>
              <button type="button" className="export-background-link" onClick={handleContinueDashboard}>
                Continuar no dashboard
              </button>
            </div>
          </div>
        )}
        {renderState === 'ready' && (
          <div className="export-status export-status--ready" role="status" aria-live="polite">
            <Check size={14} />
            <div className="export-status__body">
              <strong>Revisão {composition?.renderedRevision ?? 0}</strong> · {renderedWhen}
              {hasUnrenderedChanges && (
                <div className="export-status__note">Há uma nova edição aguardando renderização.</div>
              )}
            </div>
          </div>
        )}
        {renderState === 'error' && (
          <div className="export-status export-status--error">
            <div className="export-status__body">Erro: {error}</div>
            <button type="button" className="export-status__retry" onClick={handleRender}>
              Tentar novamente
            </button>
          </div>
        )}

        {restoreMessage && (
          <p className="export-restore-message" role="status">{restoreMessage}</p>
        )}

        {activeReceipt && (
          <section className="export-receipt" aria-labelledby="active-revision-receipt">
            <h3 id="active-revision-receipt">
              {activeReceipt.status === 'rendering' ? 'O que entra' : 'O que entrou'} na revisão {activeReceipt.revision}
            </h3>
            <ul>
              {activeReceipt.changes.map((change) => <li key={change}>{change}</li>)}
            </ul>
          </section>
        )}

        {/* Download — só habilita fora do render (fim da corrida que baixava a versão antiga) */}
        <button
          type="button"
          className={`export-download${downloadIsPrevious && renderState !== 'rendering' ? ' export-download--previous' : ''}`}
          onClick={handleDownload}
          disabled={downloading || renderState === 'rendering'}
        >
          {renderState === 'rendering' ? (
            <>
              <Loader2 size={16} className="export-status__spinner" />
              Renderizando… aguarde
            </>
          ) : downloading ? (
            <>
              <Loader2 size={16} className="export-status__spinner" />
              {dlProgress != null ? `Baixando… ${Math.round(dlProgress * 100)}%` : 'Baixando…'}
            </>
          ) : (
            <>
              <Download size={16} />
              {downloadIsPrevious ? 'Baixar versão anterior' : 'Baixar vídeo atual'}
            </>
          )}
        </button>
        {downloadIsPrevious && renderState !== 'rendering' && !downloading && (
          <p className="export-download__hint">
            Esta é a última versão renderizada — não inclui edições ainda não aplicadas.
          </p>
        )}

        {completedHistory.length > 0 && (
          <section className="export-history" aria-labelledby="revision-history-title">
            <h3 id="revision-history-title">Histórico de revisões</h3>
            <div className="export-history__list">
              {completedHistory.map((entry) => (
                <article className="export-history__item" key={entry.revision}>
                  <div className="export-history__head">
                    <strong>Revisão {entry.revision}</strong>
                    <span>{entry.author}</span>
                  </div>
                  <p>
                    {entry.renderedAt
                      ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(Date.parse(entry.renderedAt))
                      : 'Data original indisponível'}
                  </p>
                  <ul>
                    {entry.changes.map((change) => <li key={change}>{change}</li>)}
                  </ul>
                  <div className="export-history__actions">
                    <button
                      type="button"
                      onClick={() => void handleRevisionDownload(entry.revision)}
                      disabled={revisionDownloading !== null || renderState === 'rendering'}
                    >
                      <Download size={13} />
                      {revisionDownloading === entry.revision ? 'Baixando…' : `Baixar revisão ${entry.revision}`}
                    </button>
                    {entry.restorable && entry.revision !== composition?.renderedRevision && (
                      <button
                        type="button"
                        onClick={() => handleRestoreRevision(entry.revision)}
                        disabled={renderState === 'rendering'}
                      >
                        <RotateCcw size={13} />
                        Restaurar ajustes da revisão {entry.revision}
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        <h3 className="export-panel__subtitle">Compartilhar nas redes</h3>

        <div>
          {captions.map((item, i) => (
            <div key={item.platform} className="export-caption">
              <div className="export-caption__head">
                <div className="export-caption__platform">
                  <span className="export-caption__icon">{item.icon}</span>
                  {item.platform}
                </div>
                <button
                  type="button"
                  className={`export-caption__copy${copiedIndex === i ? ' export-caption__copy--copied' : ''}`}
                  onClick={() => copyToClipboard(item.caption, i)}
                >
                  {copiedIndex === i ? 'Copiado!' : 'Copiar'}
                </button>
              </div>
              <textarea
                className="export-caption__textarea"
                value={item.caption}
                onChange={(e) => updateCaption(i, e.target.value)}
                rows={3}
              />
              {item.maxChars && (
                <div className={`export-caption__count${item.caption.length >= item.maxChars ? ' export-caption__count--limit' : ''}`}>
                  {item.caption.length}/{item.maxChars}
                </div>
              )}
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  )
}
