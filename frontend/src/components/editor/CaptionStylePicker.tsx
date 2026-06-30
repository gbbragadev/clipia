'use client'

import { useEditor } from '@/contexts/EditorContext'
import type { CaptionStylePreset } from '@/remotion/types'

const PRESETS: {
  key: CaptionStylePreset
  label: string
  preview: React.CSSProperties
}[] = [
  {
    key: 'minimal',
    label: 'Minimal',
    preview: {
      fontFamily: 'Montserrat, sans-serif',
      fontSize: 13,
      fontWeight: 800,
      color: '#FFFFFF',
      textTransform: 'uppercase',
      backgroundColor: 'rgba(0, 0, 0, 0.6)',
      padding: '2px 6px',
      borderRadius: 4,
    },
  },
  {
    key: 'tiktok',
    label: 'TikTok',
    preview: {
      fontFamily: 'Inter, system-ui, sans-serif',
      fontSize: 13,
      fontWeight: 700,
      color: '#FFFFFF',
      backgroundColor: 'rgba(0, 0, 0, 0.65)',
      padding: '2px 6px',
      borderRadius: 4,
    },
  },
  {
    key: 'impact',
    label: 'Impact',
    preview: {
      fontFamily: 'Montserrat, system-ui, sans-serif',
      fontSize: 15,
      fontWeight: 900,
      color: '#FFFFFF',
      textTransform: 'uppercase',
      WebkitTextStroke: '1px #000',
      textShadow: '2px 2px 0px rgba(0, 0, 0, 0.8)',
    },
  },
  {
    key: 'karaoke',
    label: 'Karaoke',
    preview: {
      fontFamily: 'Inter, system-ui, sans-serif',
      fontSize: 13,
      fontWeight: 700,
      color: '#FFFFFF',
      background: 'linear-gradient(90deg, #FFFC00 50%, rgba(255,255,255,0.4) 50%)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      padding: '2px 6px',
    } as React.CSSProperties,
  },
  {
    key: 'boxed',
    label: 'Boxed',
    preview: {
      fontFamily: 'Montserrat, sans-serif',
      fontSize: 13,
      fontWeight: 800,
      color: '#FFFFFF',
      textTransform: 'uppercase',
      backgroundColor: 'rgba(108, 92, 231, 0.7)',
      padding: '3px 8px',
      borderRadius: 6,
    },
  },
  {
    key: 'pop',
    label: 'Pop',
    preview: {
      fontFamily: 'Montserrat, sans-serif',
      fontSize: 15,
      fontWeight: 900,
      color: '#FF6B35',
      textTransform: 'uppercase',
      WebkitTextStroke: '1px #000',
    } as React.CSSProperties,
  },
  {
    key: 'neon',
    label: 'Neon',
    preview: {
      fontFamily: 'Montserrat, sans-serif',
      fontSize: 14,
      fontWeight: 800,
      color: '#FFFFFF',
      textTransform: 'uppercase',
      textShadow: '0 0 6px #00D4FF, 0 0 14px #00D4FF',
    } as React.CSSProperties,
  },
]

const ACCENT_COLORS = [
  { label: 'Amarelo', value: '#FFFC00' },
  { label: 'TikTok Red', value: '#FE2C55' },
  { label: 'Ciano', value: '#00D4FF' },
  { label: 'Verde', value: '#4ADE80' },
  { label: 'Laranja', value: '#FF6B35' },
]

export function CaptionStylePicker() {
  const { composition, updateSubtitleStyle } = useEditor()
  if (!composition) return null

  const style = composition.subtitleStyle
  const showAccent = style.preset === 'tiktok' || style.preset === 'impact' || style.preset === 'karaoke' || style.preset === 'boxed' || style.preset === 'pop' || style.preset === 'neon'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="editor-section-header">Estilo de legenda</div>
      <div
        style={{
          display: 'flex',
          gap: 8,
          overflowX: 'auto',
          scrollbarWidth: 'none',
          paddingBottom: 4,
        }}
      >
        {PRESETS.map((preset) => {
          const isSelected = style.preset === preset.key
          return (
            <button
              key={preset.key}
              onClick={() => updateSubtitleStyle({ preset: preset.key })}
              style={{
                minWidth: 80,
                height: 56,
                borderRadius: 8,
                border: isSelected
                  ? '2px solid #6C5CE7'
                  : '1px solid rgba(255, 255, 255, 0.1)',
                background: 'linear-gradient(135deg, #1a1a2e, #16213e)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
                cursor: 'pointer',
                padding: 4,
                flexShrink: 0,
                transition: 'border-color 0.15s ease',
              }}
            >
              <span style={preset.preview}>
                {preset.key === 'tiktok' ? (
                  <>
                    A<span style={{ color: '#FFFC00' }}>a</span>
                  </>
                ) : (
                  'Aa'
                )}
              </span>
              <span
                style={{
                  fontSize: 9,
                  color: isSelected ? '#c4b5fd' : 'rgba(255, 255, 255, 0.5)',
                  fontWeight: isSelected ? 600 : 400,
                }}
              >
                {preset.label}
              </span>
            </button>
          )
        })}
      </div>

      {showAccent && (
        <div>
          <div className="editor-section-header">Cor de destaque</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {ACCENT_COLORS.map((c) => (
              <button
                key={c.value}
                onClick={() => updateSubtitleStyle({ accentColor: c.value })}
                className={`editor-color-swatch ${style.accentColor === c.value ? 'editor-color-swatch--active' : ''}`}
                style={{ background: c.value }}
                title={c.label}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
