'use client'

import { useState, useCallback } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { getToken } from '@/lib/auth'

type ExportState = 'idle' | 'rendering' | 'done'
type Quality = '1080p' | '720p'

interface PlatformCaption {
  platform: string
  icon: string
  maxChars: number | null
  caption: string
}

export function ExportPanel({ onClose }: { onClose: () => void }) {
  const { composition, jobId } = useEditor()
  const [state, setState] = useState<ExportState>('idle')
  const [quality, setQuality] = useState<Quality>('1080p')
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  const generateCaptions = useCallback((): PlatformCaption[] => {
    const title = composition?.title || 'Meu video'
    const hashtags = '#shorts #clipia #viral'

    return [
      {
        platform: 'YouTube Shorts',
        icon: 'YT',
        maxChars: null,
        caption: `${title}\n\n${hashtags}`,
      },
      {
        platform: 'TikTok',
        icon: 'TT',
        maxChars: 150,
        caption: `${title} ${hashtags}`.slice(0, 150),
      },
      {
        platform: 'Instagram Reels',
        icon: 'IG',
        maxChars: null,
        caption: `${title}\n\n${hashtags}`,
      },
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
    } catch {
      // Fallback for older browsers
    }
  }

  const handleRender = async () => {
    setState('rendering')
    setError(null)

    try {
      const token = getToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(`/api/v1/jobs/${jobId}/render`, {
        method: 'POST',
        headers,
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Erro ${res.status}: ${errText}`)
      }

      // Poll for render completion
      const poll = async () => {
        try {
          const statusRes = await fetch(`/api/v1/jobs/${jobId}/status`, { headers })
          if (!statusRes.ok) throw new Error('Erro ao verificar status')
          const data = await statusRes.json()

          if (data.status === 'completed') {
            setDownloadUrl(`/api/v1/jobs/${jobId}/download`)
            setState('done')
          } else if (data.status === 'error') {
            throw new Error(data.error || 'Erro na renderizacao')
          } else {
            setTimeout(poll, 2000)
          }
        } catch (pollErr) {
          setError(pollErr instanceof Error ? pollErr.message : 'Erro ao verificar status')
          setState('idle')
        }
      }

      setTimeout(poll, 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao renderizar')
      setState('idle')
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          maxWidth: 480,
          width: '90%',
          background: '#222222',
          borderRadius: 16,
          padding: 24,
          position: 'relative',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            background: 'none',
            border: 'none',
            color: '#888',
            fontSize: 20,
            cursor: 'pointer',
            lineHeight: 1,
          }}
        >
          X
        </button>

        <h2 style={{ color: '#E8E8E8', margin: '0 0 20px', fontSize: 20 }}>Exportar Video</h2>

        {/* Idle: quality selector + render button */}
        {state === 'idle' && (
          <>
            <div style={{ marginBottom: 16 }}>
              <label style={{ color: '#aaa', fontSize: 13, display: 'block', marginBottom: 8 }}>
                Qualidade
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                {(['1080p', '720p'] as const).map((q) => (
                  <button
                    key={q}
                    onClick={() => setQuality(q)}
                    style={{
                      flex: 1,
                      padding: '10px 16px',
                      borderRadius: 8,
                      border: 'none',
                      background: quality === q ? '#6C5CE7' : '#2A2A2A',
                      color: quality === q ? '#fff' : '#aaa',
                      cursor: 'pointer',
                      fontSize: 14,
                      fontWeight: quality === q ? 600 : 400,
                    }}
                  >
                    {q === '1080p' ? 'Alta (1080p)' : 'Media (720p)'}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12 }}>{error}</div>
            )}

            <button
              onClick={handleRender}
              style={{
                width: '100%',
                padding: '14px 0',
                borderRadius: 10,
                border: 'none',
                background: '#6C5CE7',
                color: '#fff',
                fontSize: 16,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Iniciar Export
            </button>
          </>
        )}

        {/* Rendering: progress */}
        {state === 'rendering' && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div
              style={{
                width: '100%',
                height: 6,
                background: '#2A2A2A',
                borderRadius: 3,
                overflow: 'hidden',
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  width: '60%',
                  height: '100%',
                  background: '#6C5CE7',
                  borderRadius: 3,
                  animation: 'exportPulse 1.5s ease-in-out infinite',
                }}
              />
            </div>
            <p style={{ color: '#aaa', fontSize: 14 }}>Renderizando video...</p>
            <style>{`
              @keyframes exportPulse {
                0%, 100% { opacity: 0.6; width: 30%; }
                50% { opacity: 1; width: 80%; }
              }
            `}</style>
          </div>
        )}

        {/* Done: download + social sharing */}
        {state === 'done' && downloadUrl && (
          <>
            <a
              href={downloadUrl}
              download
              style={{
                display: 'block',
                width: '100%',
                padding: '14px 0',
                borderRadius: 10,
                border: 'none',
                background: '#10b981',
                color: '#fff',
                fontSize: 16,
                fontWeight: 600,
                textAlign: 'center',
                textDecoration: 'none',
                marginBottom: 24,
              }}
            >
              Baixar Video
            </a>

            <h3 style={{ color: '#E8E8E8', fontSize: 15, margin: '0 0 12px' }}>
              Compartilhar nas redes
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {captions.map((item, i) => (
                <div
                  key={item.platform}
                  style={{
                    background: '#2A2A2A',
                    borderRadius: 10,
                    padding: 12,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span
                        style={{
                          background: '#6C5CE7',
                          color: '#fff',
                          fontSize: 11,
                          fontWeight: 700,
                          padding: '3px 6px',
                          borderRadius: 4,
                        }}
                      >
                        {item.icon}
                      </span>
                      <span style={{ color: '#E8E8E8', fontSize: 13, fontWeight: 500 }}>
                        {item.platform}
                      </span>
                    </div>
                    <button
                      onClick={() => copyToClipboard(item.caption, i)}
                      style={{
                        background: copiedIndex === i ? '#10b981' : '#6C5CE7',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        padding: '4px 10px',
                        fontSize: 12,
                        cursor: 'pointer',
                        fontWeight: 500,
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
                      width: '100%',
                      background: '#1a1a1a',
                      border: '1px solid #333',
                      borderRadius: 6,
                      color: '#E8E8E8',
                      fontSize: 13,
                      padding: 8,
                      resize: 'vertical',
                      fontFamily: 'inherit',
                    }}
                  />
                  {item.maxChars && (
                    <div
                      style={{
                        textAlign: 'right',
                        fontSize: 11,
                        color: item.caption.length >= item.maxChars ? '#ef4444' : '#666',
                        marginTop: 4,
                      }}
                    >
                      {item.caption.length}/{item.maxChars}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
