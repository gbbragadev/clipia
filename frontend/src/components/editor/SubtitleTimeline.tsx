'use client'

import { useEffect, useRef, useCallback } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'
import { useEditor } from '@/contexts/EditorContext'

export function SubtitleTimeline() {
  const { composition, playerFrame, totalFrames } = useEditor()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !composition || composition.words.length === 0) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const targetW = Math.round(rect.width * dpr)
    const targetH = Math.round(rect.height * dpr)
    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW
      canvas.height = targetH
    }

    const ctx = canvas.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    const w = rect.width
    const h = rect.height
    ctx.clearRect(0, 0, w, h)

    const totalTime = totalFrames / composition.fps
    if (totalTime <= 0) return

    const currentTime = playerFrame / composition.fps
    const font = '500 9px Inter, system-ui, sans-serif'

    for (const word of composition.words) {
      const x1 = (word.start / totalTime) * w
      const x2 = (word.end / totalTime) * w
      const wordW = Math.max(x2 - x1, 2)

      const isActive = currentTime >= word.start && currentTime <= word.end
      const isPast = currentTime > word.end

      ctx.fillStyle = isActive
        ? 'rgba(255, 86, 56, 0.7)'
        : isPast
          ? 'rgba(255, 86, 56, 0.2)'
          : 'rgba(255, 86, 56, 0.12)'
      ctx.beginPath()
      ctx.roundRect(x1, 2, wordW - 1, h - 4, 2)
      ctx.fill()

      // Render word text if block is wide enough
      if (wordW > 20) {
        const prepared = prepareWithSegments(word.word, font)
        const layout = layoutWithLines(prepared, wordW - 4, 12)
        if (layout.lines.length > 0) {
          ctx.font = font
          ctx.fillStyle = isActive ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.5)'
          ctx.fillText(word.word, x1 + 2, h / 2 + 3, wordW - 4)
        }
      }
    }
  }, [composition, playerFrame, totalFrames])

  // Redesenha só quando o estado que o draw lê muda (frame/composição/total) —
  // playerFrame vem do polling (~10Hz), então o loop RAF de 60fps redesenhava o
  // MESMO estado 6x por frame, inclusive com o vídeo pausado. ResizeObserver
  // abaixo cobre mudanças de tamanho.
  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(rafRef.current)
  }, [draw])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(() => draw())
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [draw])

  return (
    <canvas
      ref={canvasRef}
      style={{
        height: 24,
        width: 'calc(100% - 32px)',
        display: 'block',
        margin: '0 16px',
        borderRadius: 3,
      }}
    />
  )
}
