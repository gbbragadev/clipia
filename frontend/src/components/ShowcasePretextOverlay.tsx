'use client'

import { useRef, useEffect, useState, useCallback } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

interface ShowcasePretextOverlayProps {
  phrase: string
  style: 'tiktok' | 'impact' | 'karaoke'
  accent: string
}

export default function ShowcasePretextOverlay({
  phrase,
  style,
  accent,
}: ShowcasePretextOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef<number>(0)
  const activeWordRef = useRef(0)
  const lastTickRef = useRef(0)
  const isVisibleRef = useRef(false)
  const [size, setSize] = useState({ width: 200, height: 300 })

  const font = '700 14px Inter, system-ui, sans-serif'
  const lineHeight = 18

  const words = phrase.split(' ')

  const draw = useCallback(
    (now: number) => {
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

      // Cycle active word every 300ms
      if (now - lastTickRef.current > 300) {
        lastTickRef.current = now
        activeWordRef.current = (activeWordRef.current + 1) % words.length
      }

      const activeIdx = activeWordRef.current
      const prepared = prepareWithSegments(phrase, font)
      const result = layoutWithLines(prepared, w - 24, lineHeight)

      // Position at bottom-third
      const baseY = h * 0.65
      ctx.font = font

      switch (style) {
        case 'tiktok':
          drawTiktok(ctx, result, words, activeIdx, accent, w, baseY)
          break
        case 'impact':
          drawImpact(ctx, result, words, activeIdx, accent, w, baseY, now)
          break
        case 'karaoke':
          drawKaraoke(ctx, result, words, activeIdx, accent, w, baseY)
          break
      }

      if (isVisibleRef.current) {
        rafRef.current = requestAnimationFrame(draw)
      }
    },
    [size, phrase, style, accent, words, font],
  )

  // ResizeObserver
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

  // IntersectionObserver to pause/resume
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            isVisibleRef.current = true
            lastTickRef.current = performance.now()
            rafRef.current = requestAnimationFrame(draw)
          } else {
            isVisibleRef.current = false
            if (rafRef.current) {
              cancelAnimationFrame(rafRef.current)
            }
          }
        }
      },
      { threshold: 0.1 },
    )

    observer.observe(container)

    return () => {
      observer.disconnect()
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [draw])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 5,
      }}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
    </div>
  )
}

// ── TikTok style ──
// Active word: accent color with glow + underline
// Past words: white 0.9, Future words: white 0.25
// Black stroke for readability
function drawTiktok(
  ctx: CanvasRenderingContext2D,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  activeIdx: number,
  accent: string,
  canvasW: number,
  baseY: number,
) {
  let wordIdx = 0
  let yOff = baseY

  for (const line of result.lines) {
    const lineWords = line.text.split(' ')
    // Center line
    const lineWidth = ctx.measureText(line.text).width
    let xOff = (canvasW - lineWidth) / 2

    for (const word of lineWords) {
      if (!word) continue

      const isPast = wordIdx < activeIdx
      const isActive = wordIdx === activeIdx
      const wordWidth = ctx.measureText(word).width

      // Stroke for readability
      ctx.lineWidth = 2
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.8)'
      ctx.lineJoin = 'round'
      ctx.strokeText(word, xOff, yOff)

      if (isActive) {
        // Glow
        ctx.save()
        ctx.shadowColor = accent
        ctx.shadowBlur = 8
        ctx.fillStyle = accent
        ctx.fillText(word, xOff, yOff)
        ctx.restore()

        // Underline
        ctx.fillStyle = accent
        ctx.fillRect(xOff, yOff + 3, wordWidth, 2)
      } else if (isPast) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
        ctx.fillText(word, xOff, yOff)
      } else {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.25)'
        ctx.fillText(word, xOff, yOff)
      }

      xOff += ctx.measureText(word + ' ').width
      wordIdx++
    }
    yOff += 18
  }
}

// ── Impact style ──
// ALL words visible, alternating colors (odd=white, even=accent)
// Heavy stroke. Active word has scale pulse 1.05->1.0
function drawImpact(
  ctx: CanvasRenderingContext2D,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  activeIdx: number,
  accent: string,
  canvasW: number,
  baseY: number,
  now: number,
) {
  let wordIdx = 0
  let yOff = baseY

  // Pulse: oscillate between 1.0 and 1.05
  const pulse = 1.0 + 0.05 * Math.abs(Math.sin(now * 0.005))

  for (const line of result.lines) {
    const lineWords = line.text.split(' ')
    const lineWidth = ctx.measureText(line.text).width
    let xOff = (canvasW - lineWidth) / 2

    for (const word of lineWords) {
      if (!word) continue

      const isActive = wordIdx === activeIdx
      const isEven = wordIdx % 2 === 0
      const wordWidth = ctx.measureText(word).width

      ctx.save()

      if (isActive) {
        const cx = xOff + wordWidth / 2
        const cy = yOff - 5
        ctx.translate(cx, cy)
        ctx.scale(pulse, pulse)
        ctx.translate(-cx, -cy)
      }

      // Heavy stroke
      ctx.lineWidth = 3
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)'
      ctx.lineJoin = 'round'
      ctx.strokeText(word, xOff, yOff)

      ctx.fillStyle = isEven ? 'rgba(255, 255, 255, 1)' : accent
      ctx.fillText(word, xOff, yOff)
      ctx.restore()

      xOff += ctx.measureText(word + ' ').width
      wordIdx++
    }
    yOff += 18
  }
}

// ── Karaoke style ──
// Progressive fill: past words fully accent, future white 0.4
// Active word has gradient sweep
function drawKaraoke(
  ctx: CanvasRenderingContext2D,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  activeIdx: number,
  accent: string,
  canvasW: number,
  baseY: number,
) {
  let wordIdx = 0
  let yOff = baseY

  for (const line of result.lines) {
    const lineWords = line.text.split(' ')
    const lineWidth = ctx.measureText(line.text).width
    let xOff = (canvasW - lineWidth) / 2

    for (const word of lineWords) {
      if (!word) continue

      const isPast = wordIdx < activeIdx
      const isActive = wordIdx === activeIdx
      const wordWidth = ctx.measureText(word).width

      // Light stroke for readability
      ctx.lineWidth = 2
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.lineJoin = 'round'
      ctx.strokeText(word, xOff, yOff)

      if (isPast) {
        ctx.fillStyle = accent
        ctx.fillText(word, xOff, yOff)
      } else if (isActive) {
        // Gradient sweep on active word
        const grad = ctx.createLinearGradient(xOff, 0, xOff + wordWidth, 0)
        grad.addColorStop(0, accent)
        grad.addColorStop(0.6, accent)
        grad.addColorStop(0.8, 'rgba(255, 255, 255, 0.4)')
        grad.addColorStop(1, 'rgba(255, 255, 255, 0.4)')
        ctx.fillStyle = grad
        ctx.fillText(word, xOff, yOff)
      } else {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
        ctx.fillText(word, xOff, yOff)
      }

      xOff += ctx.measureText(word + ' ').width
      wordIdx++
    }
    yOff += 18
  }
}
