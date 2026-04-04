'use client'

interface FilterOption {
  value: string
  label: string
  count?: number
}

interface FilterBarProps {
  filters: {
    label: string
    options: FilterOption[]
    value: string
    onChange: (value: string) => void
  }[]
}

export default function FilterBar({ filters }: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-4 mb-4">
      {filters.map((filter) => (
        <div key={filter.label} className="flex items-center gap-1.5">
          <span className="text-xs font-medium mr-1" style={{ color: 'var(--text-tertiary)' }}>
            {filter.label}:
          </span>
          {filter.options.map((opt) => {
            const active = filter.value === opt.value
            return (
              <button
                key={opt.value}
                onClick={() => filter.onChange(opt.value)}
                className="px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer"
                style={{
                  background: active ? 'rgba(168, 85, 247, 0.15)' : 'transparent',
                  color: active ? '#c084fc' : 'var(--text-tertiary)',
                  border: active ? '1px solid rgba(168, 85, 247, 0.3)' : '1px solid transparent',
                }}
              >
                {opt.label}
                {opt.count !== undefined && (
                  <span className="ml-1 opacity-60">({opt.count})</span>
                )}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
