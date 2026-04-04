'use client'

const TEMPLATES = [
  { id: 'stock_narration', name: 'Narração + Stock', desc: 'Vídeos com footage profissional e narração', icon: '🎬' },
  { id: 'gameplay_split', name: 'Gameplay Split', desc: 'Fatos curiosos com gameplay embaixo', icon: '🎮' },
  { id: 'character_narration', name: 'Personagem', desc: 'Narração com personagem animado', icon: '🎭' },
  { id: 'story_time', name: 'Story Time', desc: 'Histórias envolventes estilo Reddit', icon: '📖' },
]

interface TemplateSelectorProps {
  selected: string
  onSelect: (id: string) => void
  disabled?: boolean
}

export default function TemplateSelector({ selected, onSelect, disabled }: TemplateSelectorProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {TEMPLATES.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t.id)}
          disabled={disabled}
          className={`flex items-start gap-3 p-4 rounded-xl border text-left transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
            selected === t.id
              ? 'bg-purple-500/10 border-purple-500/60'
              : 'bg-[#1A1A1A] border-[#333] hover:border-[#555]'
          }`}
        >
          <span className="text-3xl flex-shrink-0 mt-0.5">{t.icon}</span>
          <div className="min-w-0">
            <div className={`text-sm font-semibold ${selected === t.id ? 'text-gray-100' : 'text-gray-300'}`}>
              {t.name}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">{t.desc}</div>
          </div>
        </button>
      ))}
    </div>
  )
}
