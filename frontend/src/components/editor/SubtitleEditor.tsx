'use client'

import { useEditor } from '@/contexts/EditorContext'
import { CaptionStylePicker } from './CaptionStylePicker'

const FONT_OPTIONS = [
  'Montserrat, sans-serif',
  'Poppins, sans-serif',
  'Inter, sans-serif',
  'Roboto, sans-serif',
  'Bebas Neue, sans-serif',
  'Oswald, sans-serif',
  'Anton, sans-serif',
  'Permanent Marker, cursive',
]

const COLOR_PRESETS = [
  { label: 'Branco', value: '#FFFFFF' },
  { label: 'Amarelo', value: '#FACC15' },
  { label: 'Ciano', value: '#22D3EE' },
  { label: 'Verde neon', value: '#4ADE80' },
  { label: 'Rosa', value: '#F472B6' },
  { label: 'Laranja', value: '#FB923C' },
]

const BG_PRESETS = [
  { label: 'Escuro', value: 'rgba(0, 0, 0, 0.6)' },
  { label: 'Mais escuro', value: 'rgba(0, 0, 0, 0.85)' },
  { label: 'Roxo', value: 'rgba(124, 58, 237, 0.5)' },
  { label: 'Sem fundo', value: 'transparent' },
]

const ANIMATION_OPTIONS = [
  { label: 'Pop (scale)', value: 'pop' },
  { label: 'Fade', value: 'fade' },
  { label: 'Slide up', value: 'slideUp' },
  { label: 'Nenhuma', value: 'none' },
]

export function SubtitleEditor() {
  const { composition, updateSubtitleStyle } = useEditor()
  if (!composition) return null

  const style = composition.subtitleStyle

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Caption Style Preset Picker */}
      <CaptionStylePicker />

      {/* Font */}
      <div>
        <div className="editor-section-header">Fonte</div>
        <select
          className="editor-select"
          value={style.fontFamily}
          onChange={(e) => updateSubtitleStyle({ fontFamily: e.target.value })}
        >
          {FONT_OPTIONS.map((f) => (
            <option key={f} value={f} style={{ fontFamily: f }}>
              {f.split(',')[0]}
            </option>
          ))}
        </select>
      </div>

      {/* Size */}
      <div>
        <div className="editor-section-header">
          Tamanho &middot; {style.fontSize}px
        </div>
        <input
          type="range"
          className="editor-slider"
          min={28}
          max={80}
          value={style.fontSize}
          onChange={(e) => updateSubtitleStyle({ fontSize: Number(e.target.value) })}
        />
      </div>

      {/* Text Color */}
      <div>
        <div className="editor-section-header">Cor do texto</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {COLOR_PRESETS.map((c) => (
            <button
              key={c.value}
              onClick={() => updateSubtitleStyle({ color: c.value })}
              className={`editor-color-swatch ${style.color === c.value ? 'editor-color-swatch--active' : ''}`}
              style={{ background: c.value }}
              title={c.label}
            />
          ))}
        </div>
      </div>

      {/* Background */}
      <div>
        <div className="editor-section-header">Fundo da legenda</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {BG_PRESETS.map((c) => (
            <button
              key={c.value}
              onClick={() => updateSubtitleStyle({ backgroundColor: c.value })}
              className={`editor-color-swatch ${style.backgroundColor === c.value ? 'editor-color-swatch--active' : ''}`}
              style={{
                background: c.value === 'transparent'
                  ? 'repeating-conic-gradient(rgba(255,255,255,0.1) 0% 25%, transparent 0% 50%) 50% / 10px 10px'
                  : c.value,
              }}
              title={c.label}
            />
          ))}
        </div>
      </div>

      {/* Position */}
      <div>
        <div className="editor-section-header">Posicao</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['bottom', 'center'] as const).map((pos) => (
            <button
              key={pos}
              onClick={() => updateSubtitleStyle({ position: pos })}
              className={`editor-btn-sm ${style.position === pos ? '' : ''}`}
              style={{
                background: style.position === pos ? 'rgba(124, 58, 237, 0.2)' : undefined,
                borderColor: style.position === pos ? 'rgba(124, 58, 237, 0.4)' : undefined,
                color: style.position === pos ? '#c4b5fd' : undefined,
              }}
            >
              {pos === 'bottom' ? 'Inferior' : 'Central'}
            </button>
          ))}
        </div>
      </div>

      {/* Words per chunk */}
      <div>
        <div className="editor-section-header">
          Palavras por bloco &middot; {style.maxWordsPerChunk}
        </div>
        <input
          type="range"
          className="editor-slider"
          min={1}
          max={5}
          value={style.maxWordsPerChunk}
          onChange={(e) => updateSubtitleStyle({ maxWordsPerChunk: Number(e.target.value) })}
        />
      </div>

      {/* Preview */}
      <div>
        <div className="editor-section-header">Preview</div>
        <div style={{
          padding: 16, borderRadius: 10,
          background: 'linear-gradient(135deg, #1a1a2e, #16213e)',
          display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          minHeight: 100,
        }}>
          <div style={{
            padding: '8px 20px', borderRadius: 6,
            backgroundColor: style.backgroundColor,
          }}>
            <span style={{
              fontFamily: style.fontFamily,
              fontSize: Math.min(style.fontSize * 0.5, 28),
              fontWeight: 800,
              color: style.color,
              textTransform: 'uppercase',
              textShadow: `0 2px 6px ${style.outlineColor}`,
            }}>
              EXEMPLO LEGENDA
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
