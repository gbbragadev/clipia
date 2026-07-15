'use client'

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { PlayerRef } from '@remotion/player'
import type { CompositionData, Scene, SubtitleStyle, VideoOverlay, VoiceConfig } from '@/remotion/types'
import type { MusicAssetId } from '@/remotion/music-assets'
import { fetchComposition, saveEditorState } from '@/lib/editor-api'
import { reorderComposition } from '@/lib/editor-timeline'

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
  saveError: boolean
  retrySave: () => void
  /** Cancela o debounce e salva AGORA; false = save falhou (não renderize estado velho). */
  flushSave: () => Promise<boolean>
  playerFrame: number
  isPlaying: boolean
  playerRef: React.RefObject<PlayerRef | null>
  totalFrames: number
  narrationStale: boolean

  // Actions
  selectScene: (index: number) => void
  setActivePanel: (panel: PanelKey) => void
  updateScene: (index: number, updates: Partial<Scene>) => void
  reorderScenes: (fromIndex: number, toIndex: number) => void
  updateSubtitleStyle: (updates: Partial<SubtitleStyle>) => void
  updateVoiceConfig: (updates: Partial<VoiceConfig>) => void
  setPlayerFrame: (frame: number) => void
  seekToFrame: (frame: number) => void
  togglePlayback: () => void
  togglePanel: () => void
  addOverlay: (overlay: VideoOverlay) => void
  removeOverlay: (index: number) => void
  updateOverlay: (index: number, updates: Partial<VideoOverlay>) => void
  updateAudio: (words: Array<Record<string, unknown>>, audioUrl: string) => void
  updateMusic: (musicAssetId: MusicAssetId | null, musicVolume?: number) => void
  getSceneStartFrame: (sceneIndex: number) => number
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
  const [saveError, setSaveError] = useState(false)
  const [playerFrame, setPlayerFrame] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const playerRef = useRef<PlayerRef | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const baselineTextsRef = useRef<string[]>([])

  // Undo/redo
  const [history, setHistory] = useState<CompositionData[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const historyIndexRef = useRef(-1)

  // Derived: total frames
  const totalFrames = composition && composition.words.length > 0
    ? Math.round((composition.words[composition.words.length - 1].end + 0.5) * composition.fps)
    : 900 // 30s * 30fps fallback
  const narrationStale = composition?.narrationStale ?? false

  // Load composition
  useEffect(() => {
    fetchComposition(jobId)
      .then((data) => {
        setComposition(data)
        baselineTextsRef.current = data.scenes.map((s: Scene) => s.text)
        setHistory([data])
        setHistoryIndex(0)
        historyIndexRef.current = 0
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

  // Save com 1 retry (~2s): backend piscando não pode significar edição perdida em silêncio.
  const doSave = useCallback(async (): Promise<boolean> => {
    if (!composition) return true
    setSaving(true)
    try {
      await saveEditorState(jobId, { composition })
      setDirty(false)
      setSaveError(false)
      return true
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 2000))
      try {
        await saveEditorState(jobId, { composition })
        setDirty(false)
        setSaveError(false)
        return true
      } catch {
        // Persistiu a falha: o header mostra "Falha ao salvar" com retry manual.
        setSaveError(true)
        return false
      }
    } finally {
      setSaving(false)
    }
  }, [composition, jobId])

  // O render exporta o que está NO DISCO (script.json/editor_state.json), não o estado do
  // React: com o debounce de 1,5s, editar e exportar em seguida renderizava estado velho —
  // e debitava créditos por ele. Chamar antes de POST /render.
  // ponytail: save em voo + flush podem duplicar o mesmo payload (idempotente, inofensivo).
  const flushSave = useCallback(async (): Promise<boolean> => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
      saveTimerRef.current = null
    }
    if (!dirty) return !saveError
    return doSave()
  }, [dirty, saveError, doSave])

  // Auto-save debounce
  useEffect(() => {
    if (!dirty || !composition) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => { void doSave() }, 1500)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [dirty, composition, jobId, doSave])

  // Push to history helper — uses ref to avoid stale closure
  const pushHistory = useCallback((newComp: CompositionData) => {
    const idx = historyIndexRef.current
    setHistory((prev) => {
      const truncated = prev.slice(0, idx + 1)
      return [...truncated, newComp].slice(-MAX_HISTORY)
    })
    const newIdx = Math.min(idx + 1, MAX_HISTORY - 1)
    historyIndexRef.current = newIdx
    setHistoryIndex(newIdx)
  }, [])

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
      return {
        ...prev,
        scenes: newScenes,
        narrationStale: prev.narrationStale || (
          updates.text !== undefined
          && updates.text !== baselineTextsRef.current[index]
        ),
      }
    })
  }, [updateComposition])

  const reorderScenes = useCallback((fromIndex: number, toIndex: number) => {
    if (
      !composition
      || fromIndex === toIndex
      || fromIndex < 0
      || toIndex < 0
      || fromIndex >= composition.scenes.length
      || toIndex >= composition.scenes.length
    ) {
      return
    }

    playerRef.current?.pause()
    setIsPlaying(false)
    const next = reorderComposition(composition, fromIndex, toIndex)
    updateComposition(() => next)
    setSelectedSceneIndex(toIndex)

    const totalHints = next.scenes.reduce(
      (sum, scene) => sum + Math.max(0, scene.duration_hint),
      0,
    ) || 1
    const precedingHints = next.scenes
      .slice(0, toIndex)
      .reduce((sum, scene) => sum + Math.max(0, scene.duration_hint), 0)
    const frame = Math.round((precedingHints / totalHints) * totalFrames)
    playerRef.current?.seekTo(frame)
    setPlayerFrame(frame)
  }, [composition, totalFrames, updateComposition])

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
    updateComposition((prev) => {
      baselineTextsRef.current = prev.scenes.map((s) => s.text)
      return {
        ...prev,
        words: words as unknown as CompositionData['words'],
        audioUrl,
        narrationStale: false,
      }
    })
  }, [updateComposition])

  // Music update
  const updateMusic = useCallback((musicAssetId: MusicAssetId | null, musicVolume?: number) => {
    updateComposition((prev) => ({
      ...prev,
      musicAssetId,
      ...(musicVolume !== undefined ? { musicVolume } : {}),
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

  const updateOverlay = useCallback((index: number, updates: Partial<VideoOverlay>) => {
    updateComposition((prev) => ({
      ...prev,
      overlays: (prev.overlays || []).map((o, i) =>
        i === index ? { ...o, ...updates } : o
      ),
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

  // Get the start frame of a scene by index
  const getSceneStartFrame = useCallback((sceneIndex: number) => {
    if (!composition) return 0
    const totalHints = composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)
    let frameOffset = 0
    for (let j = 0; j < sceneIndex; j++) {
      frameOffset += (composition.scenes[j].duration_hint / totalHints) * totalFrames
    }
    return Math.round(frameOffset)
  }, [composition, totalFrames])

  // Undo/redo
  const canUndo = historyIndex > 0
  const canRedo = historyIndex < history.length - 1

  const undo = useCallback(() => {
    if (!canUndo) return
    const newIndex = historyIndex - 1
    historyIndexRef.current = newIndex
    setHistoryIndex(newIndex)
    setComposition(history[newIndex])
    setDirty(true)
  }, [canUndo, historyIndex, history])

  const redo = useCallback(() => {
    if (!canRedo) return
    const newIndex = historyIndex + 1
    historyIndexRef.current = newIndex
    setHistoryIndex(newIndex)
    setComposition(history[newIndex])
    setDirty(true)
  }, [canRedo, historyIndex, history])

  const value: EditorContextValue = {
    jobId, composition, loading, error, selectedSceneIndex, activePanel, panelCollapsed,
    dirty, saving, saveError, retrySave: doSave, flushSave, playerFrame, isPlaying, playerRef, totalFrames, narrationStale,
    selectScene, setActivePanel, updateScene, reorderScenes, updateSubtitleStyle, updateVoiceConfig,
    updateAudio, updateMusic, addOverlay, removeOverlay, updateOverlay, getSceneStartFrame,
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
