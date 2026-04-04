'use client'

import {
  splitScenes,
  countWords,
  sceneDensityRatio,
  densityColor,
  densityLabel,
  type DensityLevel,
} from '@/lib/scene-utils'

interface ScriptDensityHeatmapProps {
  script: string
  duration: number
  wpm: number
}

const COLORS: Record<DensityLevel, { border: string; bg: string; text: string }> = {
  green: { border: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)', text: '#4ade80' },
  amber: { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)', text: '#fbbf24' },
  red:   { border: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)', text: '#f87171' },
}

export default function ScriptDensityHeatmap({ script, duration, wpm }: ScriptDensityHeatmapProps) {
  const scenes = splitScenes(script)
  if (scenes.length === 0) return null

  return (
    <div className="space-y-2">
      <p className="text-xs text-[var(--text-tertiary)]">
        Densidade por cena ({scenes.length} {scenes.length === 1 ? 'cena' : 'cenas'})
      </p>
      <div className="grid gap-2">
        {scenes.map((scene, i) => {
          const words = countWords(scene)
          const ratio = sceneDensityRatio(words, wpm, duration, scenes.length)
          const level = densityColor(ratio)
          const c = COLORS[level]
          const pct = Math.min(Math.round(ratio * 100), 200)

          return (
            <div
              key={i}
              className="rounded-lg px-3 py-2 text-xs"
              style={{
                borderLeft: `3px solid ${c.border}`,
                background: c.bg,
              }}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="font-medium text-[var(--text-primary)]">Cena {i + 1}</span>
                <span style={{ color: c.text }}>
                  {words} {words === 1 ? 'palavra' : 'palavras'} &middot; {densityLabel(level)} ({pct}%)
                </span>
              </div>
              <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--bg-surface-hover)' }}>
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.min(pct, 100)}%`,
                    background: c.border,
                  }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
