'use client'

interface WpmSliderProps {
  value: number
  onChange: (v: number) => void
  disabled?: boolean
}

export default function WpmSlider({ value, onChange, disabled }: WpmSliderProps) {
  return (
    <div>
      <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">
        Velocidade de fala:{' '}
        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
          {value} palavras/min
        </span>
      </label>
      <input
        type="range"
        min={120}
        max={200}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        className="w-full accent-coral"
      />
      <div className="flex justify-between text-[10px] text-[var(--text-tertiary)] mt-0.5">
        <span>120 (lento)</span>
        <span>200 (rapido)</span>
      </div>
    </div>
  )
}
