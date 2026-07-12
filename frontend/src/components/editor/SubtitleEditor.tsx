'use client'

import { useEditor } from '@/contexts/EditorContext'
import { CaptionStylePicker } from './CaptionStylePicker'
import { ThrottledRange } from './ThrottledRange'

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
  { label: 'Coral', value: 'rgba(255, 86, 56, 0.45)' },
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
        <ThrottledRange
          min={28}
          max={80}
          value={style.fontSize}
          onCommit={(v) => updateSubtitleStyle({ fontSize: v })}
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
        <div className="editor-section-header">Posição</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['bottom', 'center'] as const).map((pos) => (
            <button
              key={pos}
              onClick={() => updateSubtitleStyle({ position: pos })}
              className={`editor-btn-sm ${style.position === pos ? '' : ''}`}
              style={{
                background: style.position === pos ? 'rgba(255, 86, 56, 0.2)' : undefined,
                borderColor: style.position === pos ? 'rgba(255, 86, 56, 0.4)' : undefined,
                color: style.position === pos ? 'var(--color-coral-soft)' : undefined,
              }}
            >
              {pos === 'bottom' ? 'Inferior' : 'Central'}
            </button>
          ))}
        </div>
      </div>

      {/* Animation */}
      <div>
        <div className="editor-section-header">Animação</div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {ANIMATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateSubtitleStyle({ animationStyle: opt.value as 'pop' | 'fade' | 'slideUp' | 'none' })}
              className="editor-btn-sm"
              style={{
                background: style.animationStyle === opt.value ? 'rgba(255,86,56,0.2)' : undefined,
                color: style.animationStyle === opt.value ? 'var(--color-coral-soft)' : undefined,
                borderColor: style.animationStyle === opt.value ? 'rgba(255,86,56,0.4)' : undefined,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stroke Width */}
      <div>
        <div className="editor-section-header">
          Contorno &middot; {style.strokeWidth}px
        </div>
        <ThrottledRange
          min={0}
          max={6}
          value={style.strokeWidth}
          onCommit={(v) => updateSubtitleStyle({ strokeWidth: v })}
        />
      </div>

      {/* Margin Bottom */}
      <div>
        <div className="editor-section-header">
          Margem inferior &middot; {style.marginBottom}px
        </div>
        <ThrottledRange
          min={40}
          max={400}
          value={style.marginBottom}
          onCommit={(v) => updateSubtitleStyle({ marginBottom: v })}
        />
      </div>

      {/* Outline Color */}
      <div>
        <div className="editor-section-header">Cor do contorno</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { label: 'Preto', value: '#000000' },
            { label: 'Escuro', value: '#1a1a1a' },
            { label: 'Roxo', value: '#6C5CE7' },
            { label: 'Azul', value: '#3b82f6' },
            { label: 'Vermelho', value: '#ef4444' },
          ].map((c) => (
            <button
              key={c.value}
              onClick={() => updateSubtitleStyle({ outlineColor: c.value })}
              className={`editor-color-swatch ${style.outlineColor === c.value ? 'editor-color-swatch--active' : ''}`}
              style={{ background: c.value, border: c.value === '#000000' ? '1px solid #444' : undefined }}
              title={c.label}
            />
          ))}
        </div>
      </div>

      {/* Words per chunk */}
      <div>
        <div className="editor-section-header">
          Palavras por bloco &middot; {style.maxWordsPerChunk}
        </div>
        <ThrottledRange
          min={1}
          max={5}
          value={style.maxWordsPerChunk}
          onCommit={(v) => updateSubtitleStyle({ maxWordsPerChunk: v })}
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
