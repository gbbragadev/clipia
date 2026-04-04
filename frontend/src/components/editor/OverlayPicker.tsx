'use client'

import { useEditor } from '@/contexts/EditorContext'
import type { VideoOverlay } from '@/remotion/types'

const OVERLAY_TEMPLATES: {
  type: VideoOverlay['type']
  label: string
  icon: string
  description: string
  getDefaults: (fps: number, totalFrames: number) => Omit<VideoOverlay, 'type'>
}[] = [
  {
    type: 'questionBox',
    label: 'Pergunta',
    icon: '❓',
    description: 'Card "VOCE SABIA?" com animacao de entrada',
    getDefaults: (fps) => ({
      startFrame: 0,
      endFrame: fps * 5,
      config: { text: 'Pergunta aqui', label: 'VOCE SABIA?' },
    }),
  },
  {
    type: 'followCTA',
    label: 'Seguir CTA',
    icon: '👆',
    description: 'Botao flutuante "SIGA PARA MAIS"',
    getDefaults: (fps) => ({
      startFrame: fps * 15,
      endFrame: fps * 25,
      config: { text: 'SIGA PARA MAIS' },
    }),
  },
  {
    type: 'endScreen',
    label: 'Tela Final',
    icon: '🎬',
    description: 'Card de finalizacao com perfil e CTA',
    getDefaults: (fps, totalFrames) => ({
      startFrame: Math.max(0, totalFrames - fps * 5),
      endFrame: totalFrames,
      config: { username: '@clipia', text: 'Gostou? Siga para mais!' },
    }),
  },
  {
    type: 'progressBar',
    label: 'Barra de Progresso',
    icon: '📊',
    description: 'Barra linear no topo do video',
    getDefaults: (_fps, totalFrames) => ({
      startFrame: 0,
      endFrame: totalFrames,
      config: {},
    }),
  },
]

const OVERLAY_TYPE_LABELS: Record<VideoOverlay['type'], string> = {
  questionBox: 'Pergunta',
  followCTA: 'Seguir CTA',
  endScreen: 'Tela Final',
  progressBar: 'Barra de Progresso',
}

export function OverlayPicker() {
  const { composition, addOverlay, removeOverlay, totalFrames } = useEditor()

  const fps = composition?.fps ?? 30
  const overlays = composition?.overlays ?? []

  const handleAdd = (template: (typeof OVERLAY_TEMPLATES)[number]) => {
    const defaults = template.getDefaults(fps, totalFrames)
    addOverlay({
      type: template.type,
      ...defaults,
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 4 }}>
      {/* Template grid */}
      <div>
        <h4 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: 'var(--editor-text, #e2e8f0)' }}>
          Adicionar Elemento
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {OVERLAY_TEMPLATES.map((t) => (
            <button
              key={t.type}
              onClick={() => handleAdd(t)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 6,
                padding: '12px 8px',
                background: 'var(--editor-surface, rgba(255,255,255,0.05))',
                border: '1px solid var(--editor-border, rgba(255,255,255,0.1))',
                borderRadius: 10,
                cursor: 'pointer',
                color: 'var(--editor-text, #e2e8f0)',
                transition: 'background 0.15s',
              }}
            >
              <span style={{ fontSize: 24 }}>{t.icon}</span>
              <span style={{ fontSize: 12, fontWeight: 600 }}>{t.label}</span>
              <span style={{ fontSize: 10, opacity: 0.6, textAlign: 'center' }}>{t.description}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Active overlays list */}
      {overlays.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: 'var(--editor-text, #e2e8f0)' }}>
            Elementos Ativos ({overlays.length})
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {overlays.map((overlay, i) => (
              <div
                key={`${overlay.type}-${i}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: 'var(--editor-surface, rgba(255,255,255,0.05))',
                  border: '1px solid var(--editor-border, rgba(255,255,255,0.1))',
                  borderRadius: 8,
                  fontSize: 12,
                  color: 'var(--editor-text, #e2e8f0)',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontWeight: 600 }}>{OVERLAY_TYPE_LABELS[overlay.type]}</span>
                  <span style={{ opacity: 0.5, fontSize: 10 }}>
                    Frame {overlay.startFrame} - {overlay.endFrame}
                  </span>
                </div>
                <button
                  onClick={() => removeOverlay(i)}
                  style={{
                    background: 'rgba(239,68,68,0.15)',
                    border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 6,
                    color: '#ef4444',
                    padding: '4px 10px',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  Remover
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
