'use client'

import { useEffect, useRef, useCallback } from 'react'
import { prepareWithSegments } from '@chenglou/pretext'

interface HowItWorksStepCanvasProps {
  number: string // "01", "02", or "03"
}

const CANVAS_W = 80
const CANVAS_H = 56
const FONT = '900 48px Inter, system-ui, sans-serif'
const COLOR = 'rgba(255, 255, 255, 0.15)'
const ANIM_DURATION = 400 // ms per digit
const STAGGER = 150 // ms delay for units digit
const GLOW_PERIOD = 3000 // ms

function easeOut(t: number): number {
  return 1 - (1 - t) * (1 - t)
}

export default function HowItWorksStepCanvas({ number }: HowItWorksStepCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animatedRef = useRef(false)
  const startTimeRef = useRef(0)
  const rafRef = useRef(0)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const now = performance.now()
    const elapsed = now - startTimeRef.current

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Use pretext to get segment data
    const prepared = prepareWithSegments(number, FONT)
    const segments = prepared.segments
    const widths = prepared.widths

    // Total width of both digits
    const totalWidth = widths[0] + widths[1]

    // Position: right-aligned within the canvas
    const startX = (CANVAS_W * dpr - totalWidth) / 2

    ctx.font = FONT
    // Scale font for DPR
    const fontSize = 48 * dpr
    ctx.font = `900 ${fontSize}px Inter, system-ui, sans-serif`

    // Re-measure at actual DPR-scaled font
    const preparedScaled = prepareWithSegments(number, `900 ${fontSize}px Inter, system-ui, sans-serif`)
    const scaledWidths = preparedScaled.widths
    const scaledTotalWidth = scaledWidths[0] + scaledWidths[1]
    const baseX = (CANVAS_W * dpr - scaledTotalWidth) / 2

    // Baseline: vertically center the 48px text in 56px canvas
    const baseY = (CANVAS_H * dpr + fontSize * 0.72) / 2

    // Glow after animation settles
    const maxSettleTime = STAGGER + ANIM_DURATION
    const settled = elapsed > maxSettleTime
    if (settled) {
      const glowElapsed = elapsed - maxSettleTime
      const glowPhase = (glowElapsed % GLOW_PERIOD) / GLOW_PERIOD
      const glowBlur = Math.sin(glowPhase * Math.PI * 2) * 4 + 4 // oscillates 0..8
      ctx.shadowColor = 'rgba(255, 255, 255, 0.3)'
      ctx.shadowBlur = glowBlur
    } else {
      ctx.shadowBlur = 0
    }

    ctx.fillStyle = COLOR

    // Draw each digit independently with slide-up offset
    for (let i = 0; i < 2; i++) {
      const digitDelay = i * STAGGER
      const digitElapsed = elapsed - digitDelay
      let yOffset: number

      if (digitElapsed <= 0) {
        // Not started yet — digit hidden (below canvas)
        continue
      } else if (digitElapsed >= ANIM_DURATION) {
        yOffset = 0
      } else {
        const progress = easeOut(digitElapsed / ANIM_DURATION)
        yOffset = (1 - progress) * fontSize
      }

      const x = baseX + (i === 0 ? 0 : scaledWidths[0])

      ctx.save()
      ctx.beginPath()
      ctx.rect(x - 2, 0, scaledWidths[i] + 4, CANVAS_H * dpr)
      ctx.clip()
      ctx.fillText(segments[i], x, baseY + yOffset)
      ctx.restore()
    }

    rafRef.current = requestAnimationFrame(draw)
  }, [number])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // Set up DPR-aware canvas
    const dpr = window.devicePixelRatio || 1
    canvas.width = CANVAS_W * dpr
    canvas.height = CANVAS_H * dpr
    canvas.style.width = `${CANVAS_W}px`
    canvas.style.height = `${CANVAS_H}px`

    // IntersectionObserver triggers animation once
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !animatedRef.current) {
          animatedRef.current = true
          startTimeRef.current = performance.now()
          rafRef.current = requestAnimationFrame(draw)
        }
      },
      { threshold: 0.3 }
    )
    observer.observe(canvas)

    return () => {
      observer.disconnect()
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [draw])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: CANVAS_W, height: CANVAS_H, display: 'block' }}
    />
  )
}
