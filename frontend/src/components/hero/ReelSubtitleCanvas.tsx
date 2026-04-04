'use client'

import { useEffect, useRef } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

interface ReelSubtitleCanvasProps {
  words: string[]
  activeWordIndex: number // -1 = none active
  accent: string          // e.g. '#22d3ee'
}

const FONT = '700 15px Inter, system-ui, sans-serif'
const LINE_HEIGHT = 20
const PADDING_X = 18
const CANVAS_HEIGHT = 50
const FONT_SIZE = 15

export default function ReelSubtitleCanvas({ words, activeWordIndex, accent }: ReelSubtitleCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const parent = canvas.parentElement
    if (!parent) return

    const dpr = window.devicePixelRatio || 1
    const w = parent.clientWidth - 48 // right: 48 offset
    const h = CANVAS_HEIGHT

    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)

    const text = words.join(' ')
    const maxWidth = w - PADDING_X * 2

    const prepared = prepareWithSegments(text, FONT)
    const layout = layoutWithLines(prepared, maxWidth, LINE_HEIGHT)

    // Center the block vertically
    const totalLines = layout.lines.length
    const blockHeight = totalLines * LINE_HEIGHT
    const startY = (h - blockHeight) / 2

    ctx.textBaseline = 'top'
    ctx.font = FONT

    // Track global word index across lines
    let globalWordIdx = 0

    for (let li = 0; li < layout.lines.length; li++) {
      const line = layout.lines[li]
      const lineY = startY + li * LINE_HEIGHT
      const lineText = line.text.trim()
      const lineWords = lineText.split(/\s+/)

      // Center line horizontally
      const x0 = PADDING_X + (maxWidth - line.width) / 2
      let x = x0

      for (let lw = 0; lw < lineWords.length; lw++) {
        const word = lineWords[lw]
        if (!word) continue

        const wordWidth = ctx.measureText(word).width
        const spaceWidth = lw < lineWords.length - 1 ? ctx.measureText(' ').width : 0

        // Determine style based on word index
        let fillColor: string
        let opacity: number
        const isActive = globalWordIdx === activeWordIndex

        if (globalWordIdx < activeWordIndex) {
          fillColor = 'white'
          opacity = 0.9
        } else if (isActive) {
          fillColor = accent
          opacity = 1
        } else {
          fillColor = 'white'
          opacity = 0.2
        }

        ctx.globalAlpha = opacity

        // Black stroke for readability (text shadow)
        ctx.strokeStyle = 'black'
        ctx.lineWidth = 3
        ctx.lineJoin = 'round'
        ctx.shadowColor = 'transparent'
        ctx.shadowBlur = 0
        ctx.strokeText(word, x, lineY)

        // Glow for active word
        if (isActive) {
          ctx.shadowColor = accent
          ctx.shadowBlur = 12
        }

        // Fill text
        ctx.fillStyle = fillColor
        ctx.fillText(word, x, lineY)

        // Underline bar for active word
        if (isActive) {
          ctx.shadowColor = 'transparent'
          ctx.shadowBlur = 0
          ctx.fillStyle = accent
          ctx.fillRect(x, lineY + FONT_SIZE + 2, wordWidth, 2)
        }

        // Reset shadow
        ctx.shadowColor = 'transparent'
        ctx.shadowBlur = 0

        x += wordWidth + spaceWidth
        globalWordIdx++
      }
    }

    ctx.globalAlpha = 1
  }, [words, activeWordIndex, accent])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        bottom: 95,
        left: 0,
        right: 48,
        height: CANVAS_HEIGHT,
        pointerEvents: 'none',
        zIndex: 2,
      }}
    />
  )
}
