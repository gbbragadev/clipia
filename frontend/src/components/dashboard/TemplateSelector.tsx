'use client'

import type { VideoTemplateInfo } from '@/lib/editor-api'

const FALLBACK_TEMPLATES: VideoTemplateInfo[] = [
  {
    id: 'stock_narration',
    name: 'Narracao + Stock',
    description: 'Videos com footage profissional e narracao',
    icon: '🎬',
    layout_type: 'fullscreen',
    credit_costs: { edge: 1, elevenlabs: 2 },
  },
  {
    id: 'gameplay_split',
    name: 'Gameplay Split',
    description: 'Fatos curiosos com gameplay embaixo',
    icon: '🎮',
    layout_type: 'split_horizontal',
    credit_costs: { edge: 1, elevenlabs: 2 },
  },
  {
    id: 'character_narration',
    name: 'Personagem',
    description: 'Narracao com personagem animado',
    icon: '🎭',
    layout_type: 'character_overlay',
    credit_costs: { edge: 1, elevenlabs: 2 },
  },
  {
    id: 'story_time',
    name: 'Story Time',
    description: 'Historias envolventes estilo Reddit',
    icon: '📖',
    layout_type: 'split_horizontal',
    credit_costs: { edge: 1, elevenlabs: 2 },
  },
  {
    id: 'novelinha_historica',
    name: 'Drama Historico',
    description: 'Narrativa com imagens IA cinematograficas',
    icon: '🎭',
    layout_type: 'fullscreen',
    media_source: 'ai_image',
    default_voice_provider: 'elevenlabs',
    credit_costs: { edge: 5, elevenlabs: 5 },
  },
]

interface TemplateSelectorProps {
  selected: string
  onSelect: (id: string) => void
  disabled?: boolean
  templates?: VideoTemplateInfo[]
}

export default function TemplateSelector({ selected, onSelect, disabled, templates }: TemplateSelectorProps) {
  const items = templates?.length ? templates : FALLBACK_TEMPLATES

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {items.map((t) => {
        const cost = t.credit_costs?.elevenlabs ?? t.credit_costs?.edge ?? 1

        return (
          <button
            key={t.id}
            onClick={() => onSelect(t.id)}
            disabled={disabled}
            className={`flex items-start gap-3 p-4 rounded-xl border text-left transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
              selected === t.id
                ? 'bg-purple-500/10 border-purple-500/60'
                : 'bg-[var(--bg-surface)] border-[var(--border-default)] hover:border-[var(--border-hover)]'
            }`}
          >
            <span className="text-3xl flex-shrink-0 mt-0.5">{t.icon}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold" style={{ color: selected === t.id ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                <span>{t.name}</span>
                {t.media_source === 'ai_image' && (
                  <span className="rounded-full border border-purple-400/30 bg-purple-500/10 px-2 py-0.5 text-[10px] font-semibold text-purple-200">
                    Imagem IA
                  </span>
                )}
              </div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{t.description}</div>
              <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                {cost} credito{cost > 1 ? 's' : ''}
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
