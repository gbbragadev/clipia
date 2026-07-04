'use client'

import { useEditor } from '@/contexts/EditorContext'

export function ScriptEditor() {
  const { composition, selectedSceneIndex, selectScene, updateScene } = useEditor()
  if (!composition) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: 'rgba(255,255,255,0.7)', margin: 0 }}>
        Roteiro &middot; {composition.scenes.length} cenas
      </h3>

      {composition.scenes.map((scene, i) => {
        const isSelected = i === selectedSceneIndex
        return (
          <div
            key={i}
            onClick={() => selectScene(i)}
            style={{
              padding: 12,
              borderRadius: 10,
              background: isSelected ? 'rgba(255, 86, 56, 0.15)' : 'rgba(255,255,255,0.03)',
              border: isSelected ? '1px solid rgba(255, 86, 56, 0.4)' : '1px solid rgba(255,255,255,0.06)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.5)' }}>
                CENA {i + 1} &middot; {scene.duration_hint}s
              </span>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
                {scene.text.split(' ').length} palavras
              </span>
            </div>

            {isSelected ? (
              <textarea
                value={scene.text}
                onChange={(e) => updateScene(i, { text: e.target.value })}
                onClick={(e) => e.stopPropagation()}
                style={{
                  width: '100%',
                  minHeight: 60,
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 6,
                  color: 'white',
                  fontSize: 13,
                  lineHeight: 1.5,
                  padding: 8,
                  resize: 'vertical',
                  fontFamily: 'inherit',
                }}
              />
            ) : (
              <p style={{ margin: 0, fontSize: 13, color: 'rgba(255,255,255,0.7)', lineHeight: 1.5 }}>
                {scene.text}
              </p>
            )}

            {isSelected && (
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: 4 }}>
                  {scene.keywords_en.join(', ')}
                </span>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
