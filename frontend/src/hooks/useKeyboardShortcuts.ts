'use client'

import { useEffect } from 'react'
import { useEditor } from '@/contexts/EditorContext'

export function useKeyboardShortcuts() {
  const {
    seekToFrame, togglePlayback, togglePanel, playerFrame, totalFrames,
    composition, selectScene, undo, redo,
  } = useEditor()

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return

      const fps = composition?.fps ?? 30

      switch (e.key) {
        case ' ':
          e.preventDefault()
          togglePlayback()
          break
        case 'ArrowLeft':
          e.preventDefault()
          seekToFrame(Math.max(0, playerFrame - 1))
          break
        case 'ArrowRight':
          e.preventDefault()
          seekToFrame(Math.min(totalFrames, playerFrame + 1))
          break
        case 'j':
          seekToFrame(Math.max(0, playerFrame - fps * 5))
          break
        case 'l':
          seekToFrame(Math.min(totalFrames, playerFrame + fps * 5))
          break
        case 'Tab':
          e.preventDefault()
          togglePanel()
          break
        case 'z':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault()
            if (e.shiftKey) redo()
            else undo()
          }
          break
        case 's':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault() // prevent browser save dialog
          }
          break
        default:
          // 1-9: jump to scene
          if (/^[1-9]$/.test(e.key) && composition) {
            const sceneIndex = parseInt(e.key) - 1
            if (sceneIndex < composition.scenes.length) {
              selectScene(sceneIndex)
              // Calculate frame for this scene start
              const totalHints = composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)
              let frameOffset = 0
              for (let i = 0; i < sceneIndex; i++) {
                frameOffset += (composition.scenes[i].duration_hint / totalHints) * totalFrames
              }
              seekToFrame(Math.round(frameOffset))
            }
          }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [seekToFrame, togglePlayback, togglePanel, playerFrame, totalFrames, composition, selectScene, undo, redo])
}
