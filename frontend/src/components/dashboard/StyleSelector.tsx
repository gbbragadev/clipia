'use client'

const STYLES = [
  { value: 'educational', label: 'Educacional', icon: '📚', desc: 'Explica conceitos de forma clara' },
  { value: 'storytelling', label: 'Storytelling', icon: '📖', desc: 'Narrativa envolvente' },
  { value: 'news', label: 'Notícias', icon: '📰', desc: 'Tom jornalístico e informativo' },
  { value: 'comedy', label: 'Comédia', icon: '😂', desc: 'Leve, divertido e descontraído' },
]

export type StyleValue = string

interface StyleSelectorProps {
  selected: StyleValue
  onSelect: (value: StyleValue) => void
  disabled?: boolean
}

export default function StyleSelector({ selected, onSelect, disabled }: StyleSelectorProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-1.5 sm:gap-2">
      {STYLES.map((s) => (
        <button
          key={s.value}
          onClick={() => onSelect(s.value)}
          disabled={disabled}
          className={`p-2.5 rounded-xl border text-center transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
            selected === s.value
              ? 'bg-coral/15 border-coral'
              : 'bg-[var(--bg-surface)] border-[var(--border-default)] hover:border-[var(--border-hover)]'
          }`}
        >
          <div className="text-lg mb-0.5">{s.icon}</div>
          <div
            className="text-[10px] font-semibold leading-tight"
            style={{ color: selected === s.value ? 'var(--text-primary)' : 'var(--text-secondary)' }}
          >
            {s.label}
          </div>
        </button>
      ))}
    </div>
  )
}
