'use client'

import { useEffect, useRef, useCallback } from 'react'
import { splitSentences, countWords } from '@/lib/scene-utils'

interface NarrationTimelineRulerProps {
  script: string
  duration: number
  wpm: number
}

const SEGMENT_COLORS = [
  '#ff5638', '#ff7a61', '#3e9bff', '#06b6d4',
  '#ff5638', '#ff7a61', '#3e9bff', '#06b6d4',
]
const BAR_HEIGHT = 28
const LABEL_HEIGHT = 16
const TIMESTAMP_HEIGHT = 14

export default function NarrationTimelineRuler({ script, duration, wpm }: NarrationTimelineRulerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const sentences = splitSentences(script)
    if (sentences.length === 0) return

    const rect = container.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    const w = rect.width
    const h = BAR_HEIGHT + LABEL_HEIGHT + TIMESTAMP_HEIGHT + 8
    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`

    const ctx = canvas.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)

    const wps = wpm / 60
    let cumWords = 0
    const segments = sentences.map((s, i) => {
      const words = countWords(s)
      const startSec = cumWords / wps
      cumWords += words
      const endSec = cumWords / wps
      return { text: s, words, startSec, endSec, color: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }
    })

    const totalEstimated = cumWords / wps
    const timelineEnd = Math.max(totalEstimated, duration)
    const overflow = totalEstimated > duration

    const barY = LABEL_HEIGHT
    segments.forEach((seg) => {
      const x = (seg.startSec / timelineEnd) * w
      const segW = ((seg.endSec - seg.startSec) / timelineEnd) * w

      ctx.fillStyle = seg.color
      ctx.beginPath()
      ctx.roundRect(x + 1, barY, Math.max(segW - 2, 2), BAR_HEIGHT, 4)
      ctx.fill()

      if (segW > 30) {
        ctx.fillStyle = '#9ca3af'
        ctx.font = '10px Inter, system-ui, sans-serif'
        ctx.textAlign = 'center'
        const maxChars = Math.floor(segW / 5)
        const label = seg.text.length > maxChars ? seg.text.slice(0, maxChars) + '...' : seg.text
        ctx.fillText(label, x + segW / 2, barY - 3)
      }
    })

    if (overflow) {
      const overflowX = (duration / timelineEnd) * w
      ctx.fillStyle = 'rgba(239, 68, 68, 0.12)'
      ctx.fillRect(overflowX, barY, w - overflowX, BAR_HEIGHT)

      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = 1.5
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.moveTo(overflowX, barY - 2)
      ctx.lineTo(overflowX, barY + BAR_HEIGHT + 2)
      ctx.stroke()
      ctx.setLineDash([])
    }

    const tsY = barY + BAR_HEIGHT + 12
    ctx.fillStyle = '#6b7280'
    ctx.font = '10px Inter, system-ui, sans-serif'
    ctx.textAlign = 'center'

    const step = timelineEnd <= 30 ? 5 : timelineEnd <= 60 ? 10 : 15
    for (let t = 0; t <= timelineEnd; t += step) {
      const x = (t / timelineEnd) * w
      ctx.fillText(`${Math.round(t)}s`, Math.max(x, 12), tsY)
    }
  }, [script, duration, wpm])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(draw, 200)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [draw])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const observer = new ResizeObserver(() => draw())
    observer.observe(container)
    return () => observer.disconnect()
  }, [draw])

  const sentences = splitSentences(script)
  if (sentences.length === 0) return null

  const totalEstimated = sentences.reduce((sum, s) => sum + countWords(s), 0) / (wpm / 60)
  const overflow = totalEstimated > duration

  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <p className="text-xs text-[var(--text-tertiary)]">Timeline estimada</p>
        <span className={`text-xs font-medium ${overflow ? 'text-red-400' : 'text-emerald-400'}`}>
          {Math.round(totalEstimated)}s / {duration}s
          {overflow && ' (excede!)'}
        </span>
      </div>
      <div ref={containerRef} className="w-full">
        <canvas ref={canvasRef} className="w-full" />
      </div>
    </div>
  )
}
