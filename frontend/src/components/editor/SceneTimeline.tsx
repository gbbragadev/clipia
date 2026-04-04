'use client'

import { useEditor } from '@/contexts/EditorContext'

const SCENE_COLORS = ['#7c3aed', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

export function SceneTimeline() {
  const { composition, selectedSceneIndex, selectScene, playerFrame } = useEditor()
  if (!composition) return null

  const totalHints = composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)
  const totalFrames = composition.words.length > 0
    ? Math.round((composition.words[composition.words.length - 1].end + 0.5) * composition.fps)
    : totalHints * composition.fps

  const playheadPercent = totalFrames > 0 ? (playerFrame / totalFrames) * 100 : 0

  return (
    <div style={{ position: 'relative' }}>
      {/* Scene blocks */}
      <div style={{ display: 'flex', gap: 2, height: 36, borderRadius: 6, overflow: 'hidden' }}>
        {composition.scenes.map((scene, i) => {
          const widthPercent = (scene.duration_hint / totalHints) * 100
          const isSelected = i === selectedSceneIndex
          const color = SCENE_COLORS[i % SCENE_COLORS.length]

          return (
            <button
              key={i}
              onClick={() => selectScene(i)}
              title={scene.text.slice(0, 80)}
              style={{
                flex: `0 0 ${widthPercent}%`,
                background: isSelected
                  ? `linear-gradient(180deg, ${color}, ${color}99)`
                  : `${color}33`,
                border: 'none',
                borderBottom: isSelected ? `2px solid ${color}` : '2px solid transparent',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: isSelected ? 'white' : 'rgba(255,255,255,0.5)',
                fontSize: 10, fontWeight: 700,
                transition: 'all 0.12s ease',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <span style={{ position: 'relative', zIndex: 1 }}>
                {i + 1} &middot; {scene.duration_hint}s
              </span>
            </button>
          )
        })}
      </div>

      {/* Playhead indicator */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0,
        left: `${playheadPercent}%`,
        width: 2,
        background: 'white',
        boxShadow: '0 0 6px rgba(255,255,255,0.5)',
        borderRadius: 1,
        pointerEvents: 'none',
        transition: 'left 0.05s linear',
        opacity: playheadPercent > 0 ? 0.8 : 0,
      }} />
    </div>
  )
}
