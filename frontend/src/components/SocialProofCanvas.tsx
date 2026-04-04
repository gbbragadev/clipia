'use client'

import { useRef, useEffect, useCallback, useState } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

interface SocialProofCanvasProps {
  target: number
  suffix: string
  format: (n: number) => string
  gradientFrom: string
  gradientTo: string
}

export default function SocialProofCanvas({
  target,
  suffix,
  format,
  gradientFrom,
  gradientTo,
}: SocialProofCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef<number>(0)
  const hasAnimatedRef = useRef(false)
  const [size, setSize] = useState({ width: 120, height: 36 })

  const font = '700 28px Inter, system-ui, sans-serif'

  const drawText = useCallback(
    (value: number) => {
      const canvas = canvasRef.current
      if (!canvas) return

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const dpr = window.devicePixelRatio || 1
      const w = size.width
      const h = size.height

      canvas.width = w * dpr
      canvas.height = h * dpr
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
      ctx.scale(dpr, dpr)

      ctx.clearRect(0, 0, w, h)

      const text = format(value)

      // Use pretext to measure text width
      const prepared = prepareWithSegments(text, font)
      const result = layoutWithLines(prepared, Infinity, 36)
      const textWidth = result.lines.length > 0 ? result.lines[0].width : 0

      // Center text horizontally
      const x = (w - textWidth) / 2

      // Create gradient across the text width
      const gradient = ctx.createLinearGradient(x, 0, x + textWidth, 0)
      gradient.addColorStop(0, gradientFrom)
      gradient.addColorStop(1, gradientTo)

      ctx.font = font
      ctx.fillStyle = gradient
      ctx.textBaseline = 'middle'
      ctx.fillText(text, x, h / 2)
    },
    [size, format, gradientFrom, gradientTo, font],
  )

  // ResizeObserver for container sizing
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          setSize({ width: Math.round(width), height: Math.round(height) })
        }
      }
    })

    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  // IntersectionObserver to trigger animation
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !hasAnimatedRef.current) {
            hasAnimatedRef.current = true
            observer.disconnect()

            const duration = 1500 // 1.5s
            const startTime = performance.now()

            const animate = (now: number) => {
              const elapsed = now - startTime
              const t = Math.min(elapsed / duration, 1)
              // Ease-out cubic: 1 - (1 - t)^3
              const eased = 1 - Math.pow(1 - t, 3)
              const current = eased * target

              drawText(current)

              if (t < 1) {
                rafRef.current = requestAnimationFrame(animate)
              }
            }

            rafRef.current = requestAnimationFrame(animate)
          }
        }
      },
      { threshold: 0.3 },
    )

    observer.observe(container)

    return () => {
      observer.disconnect()
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [target, drawText])

  // Redraw on size change (keeps final frame correct after resize)
  useEffect(() => {
    if (hasAnimatedRef.current) {
      drawText(target)
    }
  }, [size, target, drawText])

  return (
    <div
      ref={containerRef}
      style={{ width: 120, height: 36 }}
      className="flex items-center justify-center"
    >
      <canvas ref={canvasRef} />
    </div>
  )
}
