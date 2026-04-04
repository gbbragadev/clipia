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

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '5px 8px',
  background: '#1E1E1E',
  border: '1px solid rgba(255,255,255,0.12)',
  borderRadius: 6,
  color: '#E8E8E8',
  fontSize: 12,
  outline: 'none',
  boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'rgba(232,232,232,0.6)',
  marginBottom: 3,
  display: 'block',
}

const sliderStyle: React.CSSProperties = {
  width: '100%',
  accentColor: '#6C5CE7',
  cursor: 'pointer',
  height: 4,
}

function OverlayEditFields({
  overlay,
  index,
  fps,
  maxSeconds,
}: {
  overlay: VideoOverlay
  index: number
  fps: number
  maxSeconds: number
}) {
  const { updateOverlay } = useEditor()

  const startSec = parseFloat((overlay.startFrame / fps).toFixed(1))
  const endSec = parseFloat((overlay.endFrame / fps).toFixed(1))

  const handleConfigChange = (key: string, value: string) => {
    updateOverlay(index, {
      config: { ...overlay.config, [key]: value },
    })
  }

  const handleStartSec = (sec: number) => {
    const clamped = Math.max(0, Math.min(sec, endSec - 0.1))
    updateOverlay(index, { startFrame: Math.round(clamped * fps) })
  }

  const handleEndSec = (sec: number) => {
    const clamped = Math.max(startSec + 0.1, Math.min(sec, maxSeconds))
    updateOverlay(index, { endFrame: Math.round(clamped * fps) })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
      {/* Type-specific config fields */}
      {overlay.type === 'questionBox' && (
        <>
          <div>
            <span style={labelStyle}>Texto da pergunta</span>
            <input
              type="text"
              value={String(overlay.config.text ?? '')}
              onChange={(e) => handleConfigChange('text', e.target.value)}
              style={inputStyle}
              placeholder="Pergunta aqui"
            />
          </div>
          <div>
            <span style={labelStyle}>Label</span>
            <input
              type="text"
              value={String(overlay.config.label ?? 'VOCE SABIA?')}
              onChange={(e) => handleConfigChange('label', e.target.value)}
              style={inputStyle}
              placeholder="VOCE SABIA?"
            />
          </div>
        </>
      )}

      {overlay.type === 'followCTA' && (
        <div>
          <span style={labelStyle}>Texto do botao</span>
          <input
            type="text"
            value={String(overlay.config.text ?? '')}
            onChange={(e) => handleConfigChange('text', e.target.value)}
            style={inputStyle}
            placeholder="SIGA PARA MAIS"
          />
        </div>
      )}

      {overlay.type === 'endScreen' && (
        <>
          <div>
            <span style={labelStyle}>Username</span>
            <input
              type="text"
              value={String(overlay.config.username ?? '')}
              onChange={(e) => handleConfigChange('username', e.target.value)}
              style={inputStyle}
              placeholder="@clipia"
            />
          </div>
          <div>
            <span style={labelStyle}>Texto CTA</span>
            <input
              type="text"
              value={String(overlay.config.text ?? '')}
              onChange={(e) => handleConfigChange('text', e.target.value)}
              style={inputStyle}
              placeholder="Gostou? Siga para mais!"
            />
          </div>
        </>
      )}

      {/* Timing controls — all overlay types */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        padding: '8px 0 0',
        borderTop: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'rgba(232,232,232,0.6)' }}>Timing</span>
          <span style={{ fontSize: 11, color: '#6C5CE7', fontWeight: 600 }}>
            {startSec.toFixed(1)}s - {endSec.toFixed(1)}s
          </span>
        </div>

        <div>
          <span style={{ ...labelStyle, fontSize: 10 }}>Inicio ({startSec.toFixed(1)}s)</span>
          <input
            type="range"
            min={0}
            max={maxSeconds}
            step={0.1}
            value={startSec}
            onChange={(e) => handleStartSec(parseFloat(e.target.value))}
            style={sliderStyle}
          />
        </div>

        <div>
          <span style={{ ...labelStyle, fontSize: 10 }}>Fim ({endSec.toFixed(1)}s)</span>
          <input
            type="range"
            min={0}
            max={maxSeconds}
            step={0.1}
            value={endSec}
            onChange={(e) => handleEndSec(parseFloat(e.target.value))}
            style={sliderStyle}
          />
        </div>
      </div>
    </div>
  )
}

export function OverlayPicker() {
  const { composition, addOverlay, removeOverlay, totalFrames } = useEditor()

  const fps = composition?.fps ?? 30
  const overlays = composition?.overlays ?? []
  const maxSeconds = parseFloat((totalFrames / fps).toFixed(1))

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
        <h4 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: '#E8E8E8' }}>
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
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 10,
                cursor: 'pointer',
                color: '#E8E8E8',
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
          <h4 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: '#E8E8E8' }}>
            Elementos Ativos ({overlays.length})
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {overlays.map((overlay, i) => (
              <div
                key={`${overlay.type}-${i}`}
                style={{
                  padding: '10px 12px',
                  background: '#2A2A2A',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8,
                  fontSize: 12,
                  color: '#E8E8E8',
                }}
              >
                {/* Header row: label + remove button */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {OVERLAY_TYPE_LABELS[overlay.type]}
                  </span>
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

                {/* Inline editing fields */}
                <OverlayEditFields
                  overlay={overlay}
                  index={i}
                  fps={fps}
                  maxSeconds={maxSeconds}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
