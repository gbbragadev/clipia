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
  /**
   * Provedor de voz selecionado no GenerateForm. O custo exibido no card reflete
   * o que sera realmente debitado (credit_cost) para aquele provedor — evita
   * discrepancia entre "preco mostrado" e "preco debitado" (BUG-002).
   */
  voiceProvider?: 'edge' | 'elevenlabs'
}

export default function TemplateSelector({ selected, onSelect, disabled, templates, voiceProvider = 'edge' }: TemplateSelectorProps) {
  const items = templates?.length ? templates : FALLBACK_TEMPLATES

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {items.map((t) => {
        // Custo que sera realmente debitado para o provedor de voz selecionado,
        // caindo para o custo base (edge) quando ausente.
        const cost = t.credit_costs?.[voiceProvider] ?? t.credit_costs?.edge ?? 1

        return (
          <button
            key={t.id}
            onClick={() => onSelect(t.id)}
            disabled={disabled}
            className={`flex items-start gap-3 p-3 sm:p-4 rounded-xl border text-left transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
              selected === t.id
                ? 'bg-coral/10 border-coral/60'
                : 'bg-[var(--bg-surface)] border-[var(--border-default)] hover:border-[var(--border-hover)]'
            }`}
          >
            <span className="text-2xl sm:text-3xl flex-shrink-0 mt-0.5">{t.icon}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold" style={{ color: selected === t.id ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                <span>{t.name}</span>
                {t.media_source === 'ai_image' && (
                  <span className="rounded-full border border-coral/30 bg-coral/10 px-2 py-0.5 text-[10px] font-semibold text-coral">
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
