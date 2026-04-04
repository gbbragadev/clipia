'use client'

const STYLES = [
  { value: 'educational' as const, label: 'Educacional', icon: '📚', desc: 'Explica conceitos de forma clara' },
  { value: 'curiosity' as const, label: 'Curiosidades', icon: '🤯', desc: 'Fatos surpreendentes e intrigantes' },
  { value: 'storytelling' as const, label: 'Storytelling', icon: '📖', desc: 'Narrativa envolvente' },
  { value: 'news' as const, label: 'Notícias', icon: '📰', desc: 'Tom jornalístico e informativo' },
] as const

export type StyleValue = (typeof STYLES)[number]['value']

interface StyleSelectorProps {
  selected: StyleValue
  onSelect: (value: StyleValue) => void
  disabled?: boolean
}

export default function StyleSelector({ selected, onSelect, disabled }: StyleSelectorProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      {STYLES.map((s) => (
        <button
          key={s.value}
          onClick={() => onSelect(s.value)}
          disabled={disabled}
          className={`p-3 rounded-xl border text-center transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
            selected === s.value
              ? 'bg-purple-500/15 border-purple-500'
              : 'bg-[#1A1A1A] border-[#333] hover:border-[#555]'
          }`}
        >
          <div className="text-xl mb-1">{s.icon}</div>
          <div className={`text-xs font-semibold ${selected === s.value ? 'text-gray-200' : 'text-gray-400'}`}>
            {s.label}
          </div>
        </button>
      ))}
    </div>
  )
}
