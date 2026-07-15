'use client'

import {
  ChevronLeft,
  ChevronRight,
  GripVertical,
  Maximize2,
  PanelRightClose,
  PanelRightOpen,
  Pause,
  Play,
  Redo2,
  Undo2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useEditor } from '@/contexts/EditorContext'
import { clampTimelineZoom, getSceneSpans } from '@/lib/editor-timeline'
import { NarrationWaveform } from './NarrationWaveform'
import { SceneThumbnail } from './SceneThumbnail'
import { SubtitleTimeline } from './SubtitleTimeline'

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const wholeSeconds = Math.floor(seconds % 60)
  const tenths = Math.floor((seconds % 1) * 10)
  return `${minutes}:${wholeSeconds.toString().padStart(2, '0')}.${tenths}`
}

function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      className="editor-timeline__tool-btn"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

export function EditorTimeline() {
  const {
    composition,
    playerFrame,
    totalFrames,
    isPlaying,
    selectedSceneIndex,
    narrationStale,
    seekToFrame,
    togglePlayback,
    selectScene,
    togglePanel,
    panelCollapsed,
    getSceneStartFrame,
    reorderScenes,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useEditor()
  const scenesRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(1)
  const [draggedScene, setDraggedScene] = useState<number | null>(null)
  const [canDrag, setCanDrag] = useState(false)

  useEffect(() => {
    const query = window.matchMedia('(pointer: fine)')
    const update = () => setCanDrag(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  const handleSceneAreaClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    if (!scenesRef.current || !composition) return
    const rect = scenesRef.current.getBoundingClientRect()
    const percent = (event.clientX - rect.left) / rect.width
    const frame = Math.round(Math.max(0, Math.min(1, percent)) * totalFrames)
    seekToFrame(frame)
  }, [composition, totalFrames, seekToFrame])

  if (!composition) return null

  const sceneSpans = getSceneSpans(composition.scenes)
  const playheadPercent = totalFrames > 0
    ? Math.max(0, Math.min(100, (playerFrame / totalFrames) * 100))
    : 0
  const currentTime = playerFrame / composition.fps
  const totalTime = totalFrames / composition.fps
  const tickStep = totalTime <= 20 ? 2 : totalTime <= 60 ? 5 : 10
  const ticks: Array<{ time: number; percent: number }> = []
  for (let time = 0; time <= totalTime; time += tickStep) {
    ticks.push({ time, percent: totalTime > 0 ? (time / totalTime) * 100 : 0 })
  }

  const changeZoom = (delta: number) => {
    setZoom((current) => clampTimelineZoom(current + delta))
  }

  return (
    <section className="editor-timeline" aria-label="Timeline do vídeo">
      <div className="editor-timeline__toolbar">
        <div className="editor-timeline__heading">
          Timeline
          {narrationStale && (
            <span className="editor-timeline__stale">Narração desatualizada</span>
          )}
        </div>
        <div className="editor-timeline__toolbar-spacer" />
        <IconButton label="Desfazer" onClick={undo} disabled={!canUndo}>
          <Undo2 aria-hidden="true" />
        </IconButton>
        <IconButton label="Refazer" onClick={redo} disabled={!canRedo}>
          <Redo2 aria-hidden="true" />
        </IconButton>
        <div className="editor-timeline__tool-separator" />
        <IconButton label="Diminuir zoom" onClick={() => changeZoom(-0.5)} disabled={zoom <= 1}>
          <ZoomOut aria-hidden="true" />
        </IconButton>
        <IconButton label="Ajustar timeline" onClick={() => setZoom(1)} disabled={zoom === 1}>
          <Maximize2 aria-hidden="true" />
        </IconButton>
        <IconButton label="Aumentar zoom" onClick={() => changeZoom(0.5)} disabled={zoom >= 3}>
          <ZoomIn aria-hidden="true" />
        </IconButton>
        <span className="editor-timeline__zoom-label" aria-live="polite">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      <div className="editor-timeline__viewport">
        <div
          className="editor-timeline__content"
          data-timeline-zoom={zoom}
          style={{ width: `${zoom * 100}%` }}
        >
          <div className="editor-timeline__ruler" aria-hidden="true">
            {ticks.map((tick) => (
              <div
                key={tick.time}
                className="editor-timeline__tick"
                style={{ left: `${tick.percent}%` }}
              >
                {tick.time}s
              </div>
            ))}
          </div>

          <div
            className="editor-timeline__scenes"
            ref={scenesRef}
            onClick={handleSceneAreaClick}
          >
            {composition.scenes.map((scene, index) => {
              const span = sceneSpans[index]
              const isActive = index === selectedSceneIndex
              return (
                <article
                  key={`${composition.sceneOrder[index]}-${index}`}
                  className={`editor-timeline__scene ${isActive ? 'editor-timeline__scene--active' : ''}`}
                  style={{ flex: `0 0 ${(span.end - span.start) * 100}%` }}
                  data-scene-index={index}
                  draggable={canDrag}
                  onDragStart={(event) => {
                    setDraggedScene(index)
                    event.dataTransfer.effectAllowed = 'move'
                    event.dataTransfer.setData('text/plain', String(index))
                  }}
                  onDragEnd={() => setDraggedScene(null)}
                  onDragOver={(event) => {
                    if (draggedScene !== null && draggedScene !== index) {
                      event.preventDefault()
                      event.dataTransfer.dropEffect = 'move'
                    }
                  }}
                  onDrop={(event) => {
                    event.preventDefault()
                    const from = draggedScene ?? Number(event.dataTransfer.getData('text/plain'))
                    if (Number.isInteger(from)) reorderScenes(from, index)
                    setDraggedScene(null)
                  }}
                  onClick={(event) => {
                    event.stopPropagation()
                    selectScene(index)
                    seekToFrame(getSceneStartFrame(index))
                  }}
                >
                  <SceneThumbnail
                    mediaUrl={composition.mediaUrls[index]}
                    sceneNumber={index + 1}
                    size="timeline"
                  />
                  <div className="editor-timeline__scene-meta">
                    <GripVertical aria-hidden="true" />
                    <span>Cena {index + 1}</span>
                    <span>{span.duration}s</span>
                  </div>
                  <div className="editor-timeline__scene-actions">
                    <button
                      type="button"
                      aria-label={`Mover cena ${index + 1} para trás`}
                      title="Mover uma posição para trás"
                      disabled={index === 0}
                      onClick={(event) => {
                        event.stopPropagation()
                        reorderScenes(index, index - 1)
                      }}
                    >
                      <ChevronLeft aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={`Mover cena ${index + 1} para frente`}
                      title="Mover uma posição para frente"
                      disabled={index === composition.scenes.length - 1}
                      onClick={(event) => {
                        event.stopPropagation()
                        reorderScenes(index, index + 1)
                      }}
                    >
                      <ChevronRight aria-hidden="true" />
                    </button>
                  </div>
                </article>
              )
            })}

            <div
              className="editor-timeline__playhead-track"
              style={{ left: `${playheadPercent}%` }}
            >
              <div className="editor-timeline__playhead" />
            </div>
          </div>

          <div className="editor-timeline__track-row">
            <span aria-hidden="true">Voz</span>
            <NarrationWaveform audioUrl={composition.audioUrl} />
          </div>
          <div className="editor-timeline__track-row editor-timeline__track-row--captions">
            <span aria-hidden="true">Texto</span>
            <SubtitleTimeline />
          </div>
        </div>
      </div>

      <div className="editor-timeline__transport">
        <button
          type="button"
          className="editor-timeline__transport-btn"
          onClick={togglePlayback}
          title="Space"
          aria-label={isPlaying ? 'Pausar' : 'Reproduzir'}
        >
          {isPlaying ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
        </button>
        <span className="editor-timeline__time">
          {formatTime(currentTime)} / {formatTime(totalTime)}
        </span>
        <div className="editor-timeline__spacer" />
        <button
          type="button"
          className="editor-timeline__transport-btn"
          onClick={togglePanel}
          title="Tab"
          aria-label={panelCollapsed ? 'Expandir painel' : 'Recolher painel'}
        >
          {panelCollapsed
            ? <PanelRightOpen aria-hidden="true" />
            : <PanelRightClose aria-hidden="true" />}
        </button>
        <span className="editor-timeline__shortcut-hint">
          Space: play &middot; ←→: frame &middot; Tab: painel
        </span>
      </div>
    </section>
  )
}
