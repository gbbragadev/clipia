'use client'

import { useRef, useEffect, useState } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { SceneThumbnail } from './SceneThumbnail'

export function SceneGrid() {
  const { composition, selectedSceneIndex, selectScene, updateScene, seekToFrame, totalFrames } = useEditor()
  // Texto da cena: rascunho LOCAL + commit em debounce/blur. updateScene por tecla
  // empilhava 1 entrada de undo por caractere (frase de 30 chars consumia o histórico
  // de 50) e recriava a composition/contexto a cada keystroke, disputando com o preview.
  const [draftText, setDraftText] = useState<string | null>(null)
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const commitDraft = (i: number, value: string) => {
    if (draftTimer.current) {
      clearTimeout(draftTimer.current)
      draftTimer.current = null
    }
    updateScene(i, { text: value })
    setDraftText(null)
  }
  const onDraftChange = (i: number, value: string) => {
    setDraftText(value)
    if (draftTimer.current) clearTimeout(draftTimer.current)
    draftTimer.current = setTimeout(() => commitDraft(i, value), 400)
  }
  // Rascunho pertence à cena selecionada — não pode vazar quando a seleção muda
  // (o blur do textarea antigo já commitou o texto).
  useEffect(() => {
    setDraftText(null)
  }, [selectedSceneIndex])
  useEffect(() => () => { if (draftTimer.current) clearTimeout(draftTimer.current) }, [])
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
              <SceneThumbnail
                mediaUrl={composition.mediaUrls[i]}
                sceneNumber={i + 1}
              />
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
                  value={draftText ?? scene.text}
                  onChange={(e) => onDraftChange(i, e.target.value)}
                  onBlur={(e) => { if (draftTimer.current) commitDraft(i, e.target.value) }}
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
                <div style={{ display: 'flex', gap: 4, marginTop: 6, alignItems: 'center', flexWrap: 'wrap' }}>
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
