'use client'

import { useEffect, useRef, type RefObject } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

interface HeroTitleCanvasProps {
  targetRef: RefObject<HTMLHeadingElement | null>
}

const TITLE_TEXT = 'Crie videos curtos com IA'
const GLOW_COLOR = 'rgba(167, 139, 250, 0.4)'
const GLOW_RADIUS = 40
const SWEEP_DURATION = 4000

export default function HeroTitleCanvas({ targetRef }: HeroTitleCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const isVisibleRef = useRef(true)

  useEffect(() => {
    const canvas = canvasRef.current
    const h1 = targetRef.current
    if (!canvas || !h1) return

    // Get font from H1
    const computed = getComputedStyle(h1)
    const font = `${computed.fontWeight} ${computed.fontSize} ${computed.fontFamily}`

    // DPR-aware sizing
    const syncSize = () => {
      const rect = h1.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
      return { width: rect.width, height: rect.height, dpr }
    }

    let dims = syncSize()

    // ResizeObserver for DPR-aware resizing
    const resizeObserver = new ResizeObserver(() => {
      dims = syncSize()
    })
    resizeObserver.observe(h1)

    // IntersectionObserver to pause when offscreen
    const intersectionObserver = new IntersectionObserver(
      ([entry]) => {
        isVisibleRef.current = entry.isIntersecting
      },
      { threshold: 0 },
    )
    intersectionObserver.observe(h1)

    const ctx = canvas.getContext('2d')!
    const startTime = Date.now()

    const animate = () => {
      animRef.current = requestAnimationFrame(animate)

      if (!isVisibleRef.current) return

      const { width, height, dpr } = dims
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)

      // Measure text with Pretext
      const prepared = prepareWithSegments(TITLE_TEXT, font)
      const result = layoutWithLines(prepared, width, parseFloat(computed.lineHeight) || parseFloat(computed.fontSize) * 1.05)

      // Compute total text width (max line width)
      let totalTextWidth = 0
      for (const line of result.lines) {
        const lineWidth = ctx.measureText(line.text).width
        if (lineWidth > totalTextWidth) totalTextWidth = lineWidth
      }

      // Sweep position
      const elapsed = Date.now() - startTime
      const sweepX = ((elapsed % SWEEP_DURATION) / SWEEP_DURATION) * totalTextWidth

      // Draw glow on each line
      ctx.font = font
      let yOffset = 0
      const lineHeight = parseFloat(computed.lineHeight) || parseFloat(computed.fontSize) * 1.05

      for (const line of result.lines) {
        const textCenterY = yOffset + lineHeight * 0.5

        // Create radial gradient glow
        const gradient = ctx.createRadialGradient(
          sweepX, textCenterY, 0,
          sweepX, textCenterY, GLOW_RADIUS,
        )
        gradient.addColorStop(0, GLOW_COLOR)
        gradient.addColorStop(1, 'rgba(167, 139, 250, 0)')

        ctx.fillStyle = gradient
        ctx.fillRect(0, yOffset, width, lineHeight)

        yOffset += lineHeight
      }
    }

    // Wait for fonts before starting
    if (document.fonts?.ready) {
      document.fonts.ready.then(() => {
        dims = syncSize()
        animate()
      })
    } else {
      setTimeout(() => {
        dims = syncSize()
        animate()
      }, 200)
    }

    return () => {
      cancelAnimationFrame(animRef.current)
      resizeObserver.disconnect()
      intersectionObserver.disconnect()
    }
  }, [targetRef])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none',
        mixBlendMode: 'screen',
      }}
    />
  )
}
