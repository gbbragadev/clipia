'use client'

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { PlayerRef } from '@remotion/player'
import type { CompositionData, Scene, SubtitleStyle, VideoOverlay, VoiceConfig } from '@/remotion/types'
import { fetchComposition, saveEditorState } from '@/lib/editor-api'

type PanelKey = 'scenes' | 'voice' | 'subtitles' | 'elements' | 'ai'

interface EditorContextValue {
  // State
  jobId: string
  composition: CompositionData | null
  loading: boolean
  error: string | null
  selectedSceneIndex: number
  activePanel: PanelKey
  panelCollapsed: boolean
  dirty: boolean
  saving: boolean
  playerFrame: number
  isPlaying: boolean
  playerRef: React.RefObject<PlayerRef | null>
  totalFrames: number

  // Actions
  selectScene: (index: number) => void
  setActivePanel: (panel: PanelKey) => void
  updateScene: (index: number, updates: Partial<Scene>) => void
  updateSubtitleStyle: (updates: Partial<SubtitleStyle>) => void
  updateVoiceConfig: (updates: Partial<VoiceConfig>) => void
  setPlayerFrame: (frame: number) => void
  seekToFrame: (frame: number) => void
  togglePlayback: () => void
  togglePanel: () => void
  addOverlay: (overlay: VideoOverlay) => void
  removeOverlay: (index: number) => void
  updateAudio: (words: Array<Record<string, unknown>>, audioUrl: string) => void
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
}

const EditorContext = createContext<EditorContextValue | null>(null)

const MAX_HISTORY = 50

export function EditorProvider({ jobId, children }: { jobId: string; children: React.ReactNode }) {
  const [composition, setComposition] = useState<CompositionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSceneIndex, setSelectedSceneIndex] = useState(0)
  const [activePanel, setActivePanel] = useState<PanelKey>('scenes')
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [playerFrame, setPlayerFrame] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const playerRef = useRef<PlayerRef | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Undo/redo
  const [history, setHistory] = useState<CompositionData[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)

  // Derived: total frames
  const totalFrames = composition && composition.words.length > 0
    ? Math.round((composition.words[composition.words.length - 1].end + 0.5) * composition.fps)
    : 900 // 30s * 30fps fallback

  // Load composition
  useEffect(() => {
    fetchComposition(jobId)
      .then((data) => {
        setComposition(data)
        setHistory([data])
        setHistoryIndex(0)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [jobId])

  // Poll Remotion Player for frame sync
  useEffect(() => {
    const interval = setInterval(() => {
      const player = playerRef.current
      if (!player) return
      try {
        const frame = player.getCurrentFrame()
        setPlayerFrame(frame)
        setIsPlaying(player.isPlaying())
      } catch {
        // Player not ready yet
      }
    }, 100)
    return () => clearInterval(interval)
  }, [])

  // Auto-save debounce
  useEffect(() => {
    if (!dirty || !composition) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(async () => {
      setSaving(true)
      try {
        await saveEditorState(jobId, { composition })
        setDirty(false)
      } catch { /* silent */ } finally {
        setSaving(false)
      }
    }, 1500)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [dirty, composition, jobId])

  // Push to history helper
  const pushHistory = useCallback((newComp: CompositionData) => {
    setHistory((prev) => {
      const truncated = prev.slice(0, historyIndex + 1)
      const next = [...truncated, newComp].slice(-MAX_HISTORY)
      return next
    })
    setHistoryIndex((prev) => Math.min(prev + 1, MAX_HISTORY - 1))
  }, [historyIndex])

  // Composition updater (with history)
  const updateComposition = useCallback((updater: (prev: CompositionData) => CompositionData) => {
    setComposition((prev) => {
      if (!prev) return prev
      const next = updater(prev)
      pushHistory(next)
      return next
    })
    setDirty(true)
  }, [pushHistory])

  const selectScene = useCallback((index: number) => setSelectedSceneIndex(index), [])

  const updateScene = useCallback((index: number, updates: Partial<Scene>) => {
    updateComposition((prev) => {
      const newScenes = [...prev.scenes]
      newScenes[index] = { ...newScenes[index], ...updates }
      return { ...prev, scenes: newScenes }
    })
  }, [updateComposition])

  const updateSubtitleStyle = useCallback((updates: Partial<SubtitleStyle>) => {
    updateComposition((prev) => ({
      ...prev, subtitleStyle: { ...prev.subtitleStyle, ...updates },
    }))
  }, [updateComposition])

  const updateVoiceConfig = useCallback((updates: Partial<VoiceConfig>) => {
    updateComposition((prev) => ({
      ...prev, voiceConfig: { ...prev.voiceConfig, ...updates },
    }))
  }, [updateComposition])

  // Audio update (after TTS regeneration)
  const updateAudio = useCallback((words: Array<Record<string, unknown>>, audioUrl: string) => {
    updateComposition((prev) => ({
      ...prev,
      words: words as unknown as CompositionData['words'],
      audioUrl,
    }))
  }, [updateComposition])

  // Overlay management
  const addOverlay = useCallback((overlay: VideoOverlay) => {
    updateComposition((prev) => ({
      ...prev, overlays: [...(prev.overlays || []), overlay],
    }))
  }, [updateComposition])

  const removeOverlay = useCallback((index: number) => {
    updateComposition((prev) => ({
      ...prev, overlays: (prev.overlays || []).filter((_, i) => i !== index),
    }))
  }, [updateComposition])

  // Player controls
  const seekToFrame = useCallback((frame: number) => {
    playerRef.current?.seekTo(frame)
    setPlayerFrame(frame)
  }, [])

  const togglePlayback = useCallback(() => {
    const player = playerRef.current
    if (!player) return
    if (isPlaying) {
      player.pause()
      setIsPlaying(false)
    } else {
      player.play()
      setIsPlaying(true)
    }
  }, [isPlaying])

  const togglePanel = useCallback(() => setPanelCollapsed((p) => !p), [])

  // Undo/redo
  const canUndo = historyIndex > 0
  const canRedo = historyIndex < history.length - 1

  const undo = useCallback(() => {
    if (!canUndo) return
    const newIndex = historyIndex - 1
    setHistoryIndex(newIndex)
    setComposition(history[newIndex])
    setDirty(true)
  }, [canUndo, historyIndex, history])

  const redo = useCallback(() => {
    if (!canRedo) return
    const newIndex = historyIndex + 1
    setHistoryIndex(newIndex)
    setComposition(history[newIndex])
    setDirty(true)
  }, [canRedo, historyIndex, history])

  const value: EditorContextValue = {
    jobId, composition, loading, error, selectedSceneIndex, activePanel, panelCollapsed,
    dirty, saving, playerFrame, isPlaying, playerRef, totalFrames,
    selectScene, setActivePanel, updateScene, updateSubtitleStyle, updateVoiceConfig,
    updateAudio, addOverlay, removeOverlay,
    setPlayerFrame, seekToFrame, togglePlayback, togglePanel,
    undo, redo, canUndo, canRedo,
  }

  return <EditorContext value={value}>{children}</EditorContext>
}

export function useEditor() {
  const ctx = useContext(EditorContext)
  if (!ctx) throw new Error('useEditor must be used within EditorProvider')
  return ctx
}
