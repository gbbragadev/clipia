'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useTextLayout } from '@/hooks/useTextLayout'

interface KineticTypographyPreviewProps {
  text: string
  speed?: number
}

interface WordPosition {
  text: string
  x: number
  y: number
  revealTime: number
}

const CANVAS_W = 180
const CANVAS_H = 320
const BG_COLOR = '#0f0a1a'
const FONT = '700 16px Inter, system-ui, sans-serif'
const LINE_HEIGHT = 22
const PADDING_X = 16
const PROGRESS_HEIGHT = 3

export default function KineticTypographyPreview({ text, speed = 2 }: KineticTypographyPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const startTimeRef = useRef<number>(0)
  const [playing, setPlaying] = useState(false)
  const wordPositionsRef = useRef<WordPosition[]>([])

  const { getLayout } = useTextLayout(text, FONT)

  const computePositions = useCallback(() => {
    const result = getLayout(CANVAS_W - PADDING_X * 2, LINE_HEIGHT)
    if (!result) return

    const positions: WordPosition[] = []
    const startY = (CANVAS_H - result.height) / 2
    let wordIndex = 0

    const tempCanvas = document.createElement('canvas')
    const tempCtx = tempCanvas.getContext('2d')!
    tempCtx.font = FONT
    const spaceWidth = tempCtx.measureText(' ').width

    for (let li = 0; li < result.lines.length; li++) {
      const line = result.lines[li]
      const lineX = (CANVAS_W - line.width) / 2
      const lineY = startY + li * LINE_HEIGHT

      const words = line.text.split(/\s+/).filter(Boolean)
      let xOffset = 0

      for (const word of words) {
        const wWidth = tempCtx.measureText(word).width
        positions.push({
          text: word,
          x: lineX + xOffset,
          y: lineY,
          revealTime: (wordIndex / speed) * 1000,
        })
        xOffset += wWidth + spaceWidth
        wordIndex++
      }
    }

    wordPositionsRef.current = positions
  }, [getLayout, speed])

  useEffect(() => {
    computePositions()
  }, [computePositions])

  // Draw static frame when not playing
  const drawStatic = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = CANVAS_W * dpr
    canvas.height = CANVAS_H * dpr
    canvas.style.width = `${CANVAS_W}px`
    canvas.style.height = `${CANVAS_H}px`
    const ctx = canvas.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    ctx.fillStyle = BG_COLOR
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)

    ctx.font = FONT
    ctx.fillStyle = 'rgba(255, 255, 255, 0.15)'
    ctx.textBaseline = 'top'
    for (const wp of wordPositionsRef.current) {
      ctx.fillText(wp.text, wp.x, wp.y)
    }
  }, [])

  useEffect(() => {
    if (!playing) drawStatic()
  }, [playing, text, drawStatic])

  // Animation loop
  useEffect(() => {
    if (!playing) return

    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = CANVAS_W * dpr
    canvas.height = CANVAS_H * dpr
    const ctx = canvas.getContext('2d')!

    startTimeRef.current = performance.now()
    const totalDuration = wordPositionsRef.current.length > 0
      ? wordPositionsRef.current[wordPositionsRef.current.length - 1].revealTime + 500
      : 1000

    const animate = () => {
      const elapsed = performance.now() - startTimeRef.current

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = BG_COLOR
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)

      ctx.font = FONT
      ctx.textBaseline = 'top'

      for (const wp of wordPositionsRef.current) {
        const timeSinceReveal = elapsed - wp.revealTime
        if (timeSinceReveal < 0) continue

        const opacity = Math.min(timeSinceReveal / 150, 1)
        ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`
        ctx.fillText(wp.text, wp.x, wp.y)
      }

      // Progress bar
      const pct = Math.min(elapsed / totalDuration, 1)
      ctx.fillStyle = '#8b5cf6'
      ctx.fillRect(0, CANVAS_H - PROGRESS_HEIGHT, CANVAS_W * pct, PROGRESS_HEIGHT)

      if (elapsed < totalDuration) {
        animRef.current = requestAnimationFrame(animate)
      } else {
        setPlaying(false)
      }
    }

    animRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animRef.current)
  }, [playing])

  if (!text.trim()) return null

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="rounded-xl overflow-hidden border border-[var(--border-subtle)] relative"
        style={{ width: CANVAS_W, height: CANVAS_H }}
      >
        <canvas ref={canvasRef} className="block" />
      </div>
      <button
        type="button"
        onClick={() => {
          computePositions()
          setPlaying(!playing)
        }}
        className="px-4 py-1.5 rounded-lg text-xs font-medium bg-purple-600/20 text-purple-300 hover:bg-purple-600/30 transition cursor-pointer"
      >
        {playing ? 'Pausar' : 'Play'}
      </button>
    </div>
  )
}
