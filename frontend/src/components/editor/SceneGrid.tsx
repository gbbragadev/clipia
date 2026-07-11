'use client'

import { useRef, useEffect, useState } from 'react'
import { useEditor } from '@/contexts/EditorContext'

function SceneThumbnail({ videoUrl }: { videoUrl: string | undefined }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [thumb, setThumb] = useState<string | null>(null)

  useEffect(() => {
    if (!videoUrl) return
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.muted = true
    video.src = videoUrl
    video.currentTime = 0.5
    video.addEventListener('seeked', () => {
      const canvas = document.createElement('canvas')
      canvas.width = 120
      canvas.height = 213 // 9:16
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        setThumb(canvas.toDataURL('image/jpeg', 0.6))
      }
    }, { once: true })
    video.load()
  }, [videoUrl])

  if (!thumb) {
    return (
      <div style={{
        width: '100%', aspectRatio: '9/16',
        background: 'linear-gradient(135deg, rgba(255,86,56,0.15), rgba(62,155,255,0.1))',
        borderRadius: 6,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 20, color: 'rgba(255,255,255,0.2)',
      }}>
        ▶
      </div>
    )
  }

  return (
    <img
      src={thumb}
      alt=""
      style={{
        width: '100%', aspectRatio: '9/16', objectFit: 'cover',
        borderRadius: 6,
      }}
    />
  )
}

export function SceneGrid() {
  const { composition, selectedSceneIndex, selectScene, updateScene, seekToFrame, totalFrames } = useEditor()
  if (!composition) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="editor-section-header">
        {composition.scenes.length} cenas &middot; {composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)}s total
      </div>

      {composition.scenes.map((scene, i) => {
        const isSelected = i === selectedSceneIndex
        return (
          <div
            key={i}
            onClick={() => {
              selectScene(i)
              if (!composition) return
              const totalHints = composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)
              let frameOffset = 0
              for (let j = 0; j < i; j++) {
                frameOffset += (composition.scenes[j].duration_hint / totalHints) * totalFrames
              }
              seekToFrame(Math.round(frameOffset))
            }}
            className={`editor-card ${isSelected ? 'editor-card--selected' : ''}`}
            style={{ cursor: 'pointer', display: 'flex', gap: 10 }}
          >
            {/* Thumbnail */}
            <div style={{ flex: '0 0 64px' }}>
              <SceneThumbnail videoUrl={composition.mediaUrls[i]} />
            </div>

            {/* Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Cena {i + 1}
                </span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', background: 'rgba(255,255,255,0.05)', padding: '1px 6px', borderRadius: 3 }}>
                  {scene.duration_hint}s
                </span>
              </div>

              {isSelected ? (
                <textarea
                  value={scene.text}
                  onChange={(e) => updateScene(i, { text: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    width: '100%', minHeight: 48,
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid rgba(255, 86, 56, 0.3)',
                    borderRadius: 6,
                    color: '#e2e8f0', fontSize: 12, lineHeight: 1.5,
                    padding: 6, resize: 'vertical', fontFamily: 'inherit',
                  }}
                />
              ) : (
                <p style={{
                  margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.6)',
                  lineHeight: 1.4, overflow: 'hidden',
                  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                }}>
                  {scene.text}
                </p>
              )}

              {/* keywords_en são termos internos de busca de mídia (Pexels, em inglês) —
                  não são editáveis nem significam nada para o usuário; fora da UI. */}

              {isSelected && (
                <div style={{ display: 'flex', gap: 4, marginTop: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 9, color: '#666' }}>Transição:</span>
                  {(['none', 'fade', 'slide', 'wipe'] as const).map(t => (
                    <button
                      key={t}
                      onClick={(e) => { e.stopPropagation(); updateScene(i, { transition: t }) }}
                      className="editor-btn-sm"
                      style={{
                        background: (scene.transition || 'none') === t ? 'rgba(255,86,56,0.2)' : undefined,
                        color: (scene.transition || 'none') === t ? 'var(--color-coral)' : undefined,
                        borderColor: (scene.transition || 'none') === t ? 'rgba(255,86,56,0.3)' : undefined,
                      }}
                    >
                      {t === 'none' ? 'Sem' : t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
