'use client'

import { useState } from 'react'
import { splitScenes } from '@/lib/scene-utils'
import KineticTypographyPreview from './KineticTypographyPreview'

interface KineticPreviewPanelProps {
  script: string
}

export default function KineticPreviewPanel({ script }: KineticPreviewPanelProps) {
  const scenes = splitScenes(script)
  const [selectedScene, setSelectedScene] = useState(0)
  const [speed, setSpeed] = useState(2)

  if (scenes.length === 0) return null

  const safeIndex = Math.min(selectedScene, scenes.length - 1)

  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--text-tertiary)]">Preview de tipografia</p>

      {scenes.length > 1 && (
        <div className="flex gap-1.5 flex-wrap">
          {scenes.map((_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setSelectedScene(i)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition cursor-pointer ${
                i === safeIndex
                  ? 'bg-purple-600/30 text-purple-300'
                  : 'bg-[var(--bg-surface-hover)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
              }`}
            >
              Cena {i + 1}
            </button>
          ))}
        </div>
      )}

      <KineticTypographyPreview text={scenes[safeIndex]} speed={speed} />

      <div>
        <label className="block text-[10px] text-[var(--text-tertiary)] mb-1">
          Velocidade: {speed} palavras/s
        </label>
        <input
          type="range"
          min={1}
          max={5}
          step={0.5}
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
          className="w-full accent-purple-600"
        />
      </div>
    </div>
  )
}
