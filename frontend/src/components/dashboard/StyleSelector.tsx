'use client'

const STYLES = [
  { value: 'educational', label: 'Educacional', icon: '📚', desc: 'Explica conceitos de forma clara' },
  { value: 'curiosity', label: 'Curiosidades', icon: '🤯', desc: 'Fatos surpreendentes e intrigantes' },
  { value: 'storytelling', label: 'Storytelling', icon: '📖', desc: 'Narrativa envolvente' },
  { value: 'news', label: 'Notícias', icon: '📰', desc: 'Tom jornalístico e informativo' },
  { value: 'humor', label: 'Humor', icon: '😂', desc: 'Leve, divertido e descontraído' },
  { value: 'motivational', label: 'Motivacional', icon: '🔥', desc: 'Inspirador e energizante' },
  { value: 'conspiracy', label: 'Mistério', icon: '🕵️', desc: 'Tom misterioso e investigativo' },
  { value: 'top5', label: 'Top 5', icon: '🏆', desc: 'Rankings e listas comparativas' },
  { value: 'tutorial', label: 'Tutorial', icon: '🎓', desc: 'Passo a passo didático' },
  { value: 'debate', label: 'Debate', icon: '⚖️', desc: 'Prós e contras, dois lados' },
  { value: 'horror', label: 'Terror', icon: '👻', desc: 'Arrepiante e sombrio' },
  { value: 'scifi', label: 'Sci-Fi', icon: '🚀', desc: 'Futurista e especulativo' },
]

export type StyleValue = string

interface StyleSelectorProps {
  selected: StyleValue
  onSelect: (value: StyleValue) => void
  disabled?: boolean
}

export default function StyleSelector({ selected, onSelect, disabled }: StyleSelectorProps) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
      {STYLES.map((s) => (
        <button
          key={s.value}
          onClick={() => onSelect(s.value)}
          disabled={disabled}
          className={`p-2.5 rounded-xl border text-center transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
            selected === s.value
              ? 'bg-purple-500/15 border-purple-500'
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
