'use client'

import { useCallback, useRef } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { SubtitleTimeline } from './SubtitleTimeline'

// Cor NÃO carrega significado por cena (auditoria F0): ativa = coral, demais neutras.

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 10)
  return `${m}:${s.toString().padStart(2, '0')}.${ms}`
}

export function EditorTimeline() {
  const {
    composition, playerFrame, totalFrames, isPlaying, selectedSceneIndex,
    seekToFrame, togglePlayback, selectScene, togglePanel, panelCollapsed,
    getSceneStartFrame,
  } = useEditor()
  const scenesRef = useRef<HTMLDivElement>(null)

  const handleSceneAreaClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!scenesRef.current || !composition) return
    const rect = scenesRef.current.getBoundingClientRect()
    const percent = (e.clientX - rect.left) / rect.width
    const frame = Math.round(Math.max(0, Math.min(1, percent)) * totalFrames)
    seekToFrame(frame)
  }, [composition, totalFrames, seekToFrame])

  if (!composition) return null

  const totalHints = composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)
  const playheadPercent = totalFrames > 0 ? (playerFrame / totalFrames) * 100 : 0
  const currentTime = playerFrame / composition.fps
  const totalTime = totalFrames / composition.fps

  // Ruler ticks every 5 seconds
  const ticks = []
  for (let t = 0; t <= totalTime; t += 5) {
    ticks.push({ time: t, percent: (t / totalTime) * 100 })
  }

  return (
    <div className="editor-timeline">
      {/* Ruler */}
      <div className="editor-timeline__ruler">
        {ticks.map((tick) => (
          <div key={tick.time} className="editor-timeline__tick" style={{ left: `${tick.percent}%` }}>
            {tick.time}s
          </div>
        ))}
      </div>

      {/* Scene blocks with click-to-seek */}
      <div className="editor-timeline__scenes" ref={scenesRef} onClick={handleSceneAreaClick}>
        {composition.scenes.map((scene, i) => {
          const widthPercent = (scene.duration_hint / totalHints) * 100
          const isActive = i === selectedSceneIndex

          return (
            <div
              key={i}
              className={`editor-timeline__scene ${isActive ? 'editor-timeline__scene--active' : ''}`}
              style={{
                flex: `0 0 ${widthPercent}%`,
                background: isActive
                  ? 'linear-gradient(180deg, #ff5638, #ff5638aa)'
                  : 'rgba(255,255,255,0.08)',
              }}
              onClick={(e) => { e.stopPropagation(); selectScene(i); seekToFrame(getSceneStartFrame(i)) }}
            >
              {i + 1}
            </div>
          )
        })}

        {/* Playhead */}
        <div
          className="editor-timeline__playhead"
          style={{ left: `${playheadPercent}%` }}
        />
      </div>

      {/* Word-by-word subtitle visualization (Pretext canvas) */}
      <SubtitleTimeline />

      {/* Transport controls */}
      <div className="editor-timeline__transport">
        <button className="editor-timeline__transport-btn" onClick={togglePlayback} title="Space" aria-label={isPlaying ? "Pausar" : "Reproduzir"}>
          {isPlaying ? '⏸' : '▶'}
        </button>

        <span className="editor-timeline__time">
          {formatTime(currentTime)} / {formatTime(totalTime)}
        </span>

        <div className="editor-timeline__spacer" />

        <button
          className="editor-timeline__transport-btn"
          onClick={togglePanel}
          title="Tab"
        >
          {panelCollapsed ? '◧' : '▣'}
        </button>

        <span className="editor-timeline__shortcut-hint">
          Space: play &middot; ←→: frame &middot; Tab: painel
        </span>
      </div>
    </div>
  )
}
