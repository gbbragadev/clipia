'use client'

import { useState, useCallback, useEffect } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { useAuth } from '@/contexts/AuthContext'
import { downloadAuthenticatedFile } from '@/lib/download'
import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'
import ExportCostBanner from '@/components/dashboard/ExportCostBanner'

type RenderStatus = 'ready' | 'rendering' | 'updated' | 'error'

interface PlatformCaption {
  platform: string
  icon: string
  maxChars: number | null
  caption: string
}

export function ExportPanel({ onClose }: { onClose: () => void }) {
  const { composition, jobId, narrationStale, setActivePanel } = useEditor()
  const { user } = useAuth()
  const [renderStatus, setRenderStatus] = useState<RenderStatus>('ready')
  const [error, setError] = useState<string | null>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [rendering, setRendering] = useState(false)
  const [staleAccepted, setStaleAccepted] = useState(false)

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

  // Trigger background render
  const handleRender = async () => {
    setRendering(true)
    setError(null)
    setRenderStatus('rendering')

    try {
      const token = getToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(`/api/v1/jobs/${jobId}/render`, { method: 'POST', headers })
      if (!res.ok) throw new Error(await readApiError(res, `Erro ${res.status}`))

      // Poll in background
      const poll = async () => {
        try {
          const statusRes = await fetch(`/api/v1/jobs/${jobId}/status`, { headers })
          if (!statusRes.ok) throw new Error(await readApiError(statusRes, 'Erro ao verificar status'))
          const data = await statusRes.json()

          if (data.status === 'completed') {
            setRenderStatus('updated')
            setRendering(false)
          } else if (data.status === 'error') {
            throw new Error(data.error || 'Erro na renderizacao')
          } else {
            setTimeout(poll, 2000)
          }
        } catch (pollErr) {
          setError(pollErr instanceof Error ? pollErr.message : 'Erro')
          setRenderStatus('error')
          setRendering(false)
        }
      }
      setTimeout(poll, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao renderizar')
      setRenderStatus('error')
      setRendering(false)
    }
  }

  // Auto-trigger render on open
  useEffect(() => {
    if (!narrationStale) handleRender()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const downloadUrl = `/api/v1/jobs/${jobId}/download`

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        maxWidth: 480, width: '90%',
        background: '#222222', borderRadius: 16, padding: 24,
        position: 'relative', maxHeight: '90vh', overflowY: 'auto',
      }}>
        {/* Close */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute', top: 12, right: 12,
            background: 'none', border: 'none', color: '#888',
            fontSize: 20, cursor: 'pointer', lineHeight: 1,
          }}
        >
          X
        </button>

        <h2 style={{ color: '#E8E8E8', margin: '0 0 20px', fontSize: 20 }}>Exportar Vídeo</h2>

        {narrationStale && !staleAccepted && (
          <div style={{
            background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
            borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 13, color: '#fbbf24',
          }}>
            O texto das cenas mudou desde a última narração. Se exportar agora, o áudio e as
            legendas NÃO vão refletir o novo texto.
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button
                onClick={() => { setActivePanel('voice'); onClose() }}
                style={{ background: 'var(--color-coral)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', fontSize: 12, cursor: 'pointer' }}
              >
                Regenerar narração primeiro
              </button>
              <button
                onClick={() => { setStaleAccepted(true); handleRender() }}
                style={{ background: 'rgba(255,255,255,0.08)', color: '#ccc', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 12px', fontSize: 12, cursor: 'pointer' }}
              >
                Exportar mesmo assim
              </button>
            </div>
          </div>
        )}

        {/* Cost banner */}
        {(composition?.pendingCredits ?? 0) > 0 && (
          <div style={{ marginBottom: 12 }}>
            <ExportCostBanner
              pendingCredits={composition?.pendingCredits ?? 0}
              userCredits={user?.credits ?? 0}
            />
          </div>
        )}

        {/* Download — always available */}
        <button
          type="button"
          onClick={() => downloadAuthenticatedFile(downloadUrl, `clipia-${jobId.slice(0, 8)}.mp4`)}
          style={{
            display: 'block', width: '100%', padding: '14px 0',
            borderRadius: 10, border: 'none',
            background: '#10b981', color: '#fff',
            fontSize: 16, fontWeight: 600,
            textAlign: 'center', textDecoration: 'none',
            marginBottom: 12,
            cursor: 'pointer',
          }}
        >
          Baixar Video
        </button>

        {/* Render status badge */}
        <div style={{
          padding: '8px 12px', borderRadius: 8, marginBottom: 20,
          fontSize: 13, display: 'flex', alignItems: 'center', gap: 8,
          background: rendering ? 'rgba(255,86,56,0.1)' : renderStatus === 'updated' ? 'rgba(16,185,129,0.1)' : renderStatus === 'error' ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.03)',
          border: `1px solid ${rendering ? 'rgba(255,86,56,0.2)' : renderStatus === 'updated' ? 'rgba(16,185,129,0.2)' : renderStatus === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)'}`,
        }}>
          {rendering && (
            <>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--color-coral)',
                animation: 'pulse 1.5s ease-in-out infinite',
              }} />
              <span style={{ color: '#a78bfa' }}>Atualizando com suas edições... (~2 min)</span>
              <style>{`@keyframes pulse { 0%,100% { opacity: 0.4 } 50% { opacity: 1 } }`}</style>
              </>
          )}
          {renderStatus === 'updated' && !rendering && (
            <>
              <span style={{ color: '#10b981', fontSize: 16 }}>&#10003;</span>
              <span style={{ color: '#6ee7b7' }}>Video atualizado com suas edicoes!</span>
            </>
          )}
          {renderStatus === 'error' && !rendering && (
            <>
              <span style={{ color: '#ef4444' }}>Erro: {error}</span>
              <button
                onClick={handleRender}
                style={{
                  marginLeft: 'auto', background: 'var(--color-coral)', color: '#fff',
                  border: 'none', borderRadius: 6, padding: '4px 10px',
                  fontSize: 12, cursor: 'pointer',
                }}
              >
                Tentar novamente
              </button>
            </>
          )}
          {renderStatus === 'ready' && !rendering && (
            <span style={{ color: 'rgba(255,255,255,0.4)' }}>Versão anterior disponível para download</span>
          )}
        </div>

        {/* Social sharing captions */}
        <h3 style={{ color: '#E8E8E8', fontSize: 15, margin: '0 0 12px' }}>
          Compartilhar nas redes
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {captions.map((item, i) => (
            <div key={item.platform} style={{ background: '#2A2A2A', borderRadius: 10, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    background: 'var(--color-coral)', color: '#fff',
                    fontSize: 11, fontWeight: 700, padding: '3px 6px', borderRadius: 4,
                  }}>
                    {item.icon}
                  </span>
                  <span style={{ color: '#E8E8E8', fontSize: 13, fontWeight: 500 }}>{item.platform}</span>
                </div>
                <button
                  onClick={() => copyToClipboard(item.caption, i)}
                  style={{
                    background: copiedIndex === i ? '#10b981' : 'var(--color-coral)',
                    color: '#fff', border: 'none', borderRadius: 6,
                    padding: '4px 10px', fontSize: 12, cursor: 'pointer', fontWeight: 500,
                  }}
                >
                  {copiedIndex === i ? 'Copiado!' : 'Copiar'}
                </button>
              </div>
              <textarea
                value={item.caption}
                onChange={(e) => updateCaption(i, e.target.value)}
                rows={3}
                style={{
                  width: '100%', background: '#1a1a1a', border: '1px solid #333',
                  borderRadius: 6, color: '#E8E8E8', fontSize: 13, padding: 8,
                  resize: 'vertical', fontFamily: 'inherit',
                }}
              />
              {item.maxChars && (
                <div style={{
                  textAlign: 'right', fontSize: 11, marginTop: 4,
                  color: item.caption.length >= item.maxChars ? '#ef4444' : '#666',
                }}>
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
