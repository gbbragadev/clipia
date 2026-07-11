'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, Clapperboard, Download, Loader2, X } from 'lucide-react'
import { useEditor } from '@/contexts/EditorContext'
import { useAuth } from '@/contexts/AuthContext'
import { downloadAuthenticatedFile } from '@/lib/download'
import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'
import { useToast } from '@/components/ui/feedback'
import ExportCostBanner from '@/components/dashboard/ExportCostBanner'

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
  const { composition, jobId, narrationStale, setActivePanel } = useEditor()
  const { user } = useAuth()
  const { success: toastSuccess, error: toastError } = useToast()

  const [renderState, setRenderState] = useState<RenderState>('idle')
  const [renderProgress, setRenderProgress] = useState(0)
  const [renderDetail, setRenderDetail] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [staleAccepted, setStaleAccepted] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [dlProgress, setDlProgress] = useState<number | null>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)
  useEffect(() => {
    unmounted.current = false
    return () => {
      unmounted.current = true
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [])

  const generateCaptions = useCallback((): PlatformCaption[] => {
    const title = composition?.title || 'Meu video'
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

      if (data.status === 'completed') {
        setRenderState('ready')
        setRenderProgress(1)
        toastSuccess('Vídeo atualizado', 'Suas edições foram aplicadas ao arquivo final.')
      } else if (data.status === 'error') {
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
  }, [jobId, authHeaders, toastSuccess])

  const handleRender = useCallback(async () => {
    setError(null)
    setRenderState('rendering')
    setRenderProgress(0)
    setRenderDetail(null)
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/render`, { method: 'POST', headers: authHeaders() })
      if (!res.ok) throw new Error(await readApiError(res, `Erro ${res.status}`))
      pollTimer.current = setTimeout(pollStatus, 2000)
    } catch (err) {
      if (unmounted.current) return
      setRenderState('error')
      setError(err instanceof Error ? err.message : 'Erro ao renderizar')
    }
  }, [jobId, authHeaders, pollStatus])

  // O render NÃO dispara mais ao abrir o modal: um toque acidental em "Exportar"
  // (alvo pequeno no mobile) enfileirava ~2 min de render e debitava pending_credits
  // sem confirmação. Agora o usuário confirma no botão "Aplicar edições".
  // Escape fecha o modal (o clique no backdrop já fechava).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
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
        if (data.status === 'rendering') {
          setRenderState('rendering')
          setRenderProgress(Number(data.progress) || 0)
          setRenderDetail(typeof data.detail === 'string' && data.detail ? data.detail : null)
          pollTimer.current = setTimeout(pollStatus, 2500)
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

  const downloadIsPrevious = renderState !== 'ready'

  return (
    <div className="export-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="export-panel" role="dialog" aria-modal="true" aria-label="Exportar vídeo">
        <button type="button" className="export-panel__close" onClick={onClose} aria-label="Fechar">
          <X size={16} />
        </button>

        <h2 className="export-panel__title">Exportar vídeo</h2>

        {narrationStale && !staleAccepted && (
          <div className="export-stale">
            O texto das cenas mudou desde a última narração. Se exportar agora, o áudio e as
            legendas NÃO vão refletir o novo texto.
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

        {(composition?.pendingCredits ?? 0) > 0 && (
          <div style={{ marginBottom: 12 }}>
            <ExportCostBanner
              pendingCredits={composition?.pendingCredits ?? 0}
              userCredits={user?.credits ?? 0}
            />
          </div>
        )}

        {/* Confirmação explícita do render (custo + ~2 min ficam claros ANTES de disparar) */}
        {renderState === 'idle' && !(narrationStale && !staleAccepted) && (
          <button type="button" className="export-download" onClick={handleRender}>
            <Clapperboard size={16} />
            Aplicar edições e renderizar (~2 min)
            {(composition?.pendingCredits ?? 0) > 0 && ` · ${composition?.pendingCredits} créd.`}
          </button>
        )}

        {/* Status do render */}
        {renderState === 'rendering' && (
          <div className="export-status export-status--rendering">
            <Loader2 size={14} className="export-status__spinner" />
            <div className="export-status__body">
              <div>{renderDetail || 'Aplicando suas edições… (~2 min)'}</div>
              <div className="export-progress">
                <div className="export-progress__fill" style={{ width: `${Math.max(6, renderProgress * 100)}%` }} />
              </div>
            </div>
          </div>
        )}
        {renderState === 'ready' && (
          <div className="export-status export-status--ready">
            <Check size={14} />
            <div className="export-status__body">Vídeo atualizado com suas edições!</div>
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
              {downloadIsPrevious ? 'Baixar versão anterior' : 'Baixar vídeo'}
            </>
          )}
        </button>
        {downloadIsPrevious && renderState !== 'rendering' && !downloading && (
          <p className="export-download__hint">
            Esta é a última versão renderizada — não inclui edições ainda não aplicadas.
          </p>
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
      </div>
    </div>
  )
}
