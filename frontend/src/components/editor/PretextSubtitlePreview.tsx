'use client'

import { useEffect, useRef, useCallback } from 'react'
import { prepareWithSegments, layoutWithLines, walkLineRanges } from '@chenglou/pretext'
import { useEditor } from '@/contexts/EditorContext'

export function PretextSubtitlePreview() {
  const { composition, playerFrame, totalFrames } = useEditor()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !composition || !composition.words.length) return

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

    const style = composition.subtitleStyle
    const currentTime = playerFrame / composition.fps
    const maxWords = style.maxWordsPerChunk

    // Find active word chunk
    const words = composition.words
    let chunkStart = -1
    let chunkEnd = -1
    for (let i = 0; i < words.length; i += maxWords) {
      const end = Math.min(i + maxWords, words.length)
      const group = words.slice(i, end)
      if (currentTime >= group[0].start && currentTime <= group[group.length - 1].end) {
        chunkStart = i
        chunkEnd = end
        break
      }
    }

    if (chunkStart < 0) return

    const chunkWords = words.slice(chunkStart, chunkEnd)
    const text = chunkWords.map(cw => cw.word).join(' ').toUpperCase()

    // Scale to canvas (original 1080x1920)
    const scale = w / 1080
    const fontSize = Math.max(12, Math.round(style.fontSize * scale))
    const fontWeight = style.preset === 'impact' ? 900 : 800
    const font = `${fontWeight} ${fontSize}px ${style.fontFamily}`

    const prepared = prepareWithSegments(text, font)
    const maxTextWidth = w * 0.85
    const lineHeight = fontSize * 1.3
    const layout = layoutWithLines(prepared, maxTextWidth, lineHeight)

    // Position
    const textHeight = layout.lines.length * lineHeight
    const marginBottom = style.marginBottom * scale
    const yBase = style.position === 'bottom'
      ? h - marginBottom - textHeight
      : (h - textHeight) / 2

    // Animation
    const chunkTime = chunkWords[0].start
    const elapsed = currentTime - chunkTime
    const animStyle = style.animationStyle || 'pop'

    let fadeProgress = 1
    let scaleVal = 1
    let yOffset = 0

    if (animStyle === 'pop' || animStyle === 'fade') {
      fadeProgress = Math.min(1, elapsed / 0.12)
    }
    if (animStyle === 'pop') {
      scaleVal = 0.85 + 0.15 * Math.min(1, elapsed / 0.15)
    }
    if (animStyle === 'slideUp') {
      fadeProgress = Math.min(1, elapsed / 0.12)
      yOffset = 25 * (1 - Math.min(1, elapsed / 0.15))
    }

    ctx.save()
    ctx.globalAlpha = fadeProgress

    // Apply scale transform from center
    if (scaleVal !== 1) {
      const cx = w / 2
      const cy = yBase + textHeight / 2
      ctx.translate(cx, cy)
      ctx.scale(scaleVal, scaleVal)
      ctx.translate(-cx, -cy)
    }

    // Background
    if (style.backgroundColor !== 'transparent') {
      const padding = 14 * scale
      const maxLineWidth = Math.max(...layout.lines.map(l => l.width), 0)
      const bgX = (w - maxLineWidth) / 2 - padding
      const bgY = yBase - padding / 2 + yOffset
      const bgW = maxLineWidth + padding * 2
      const bgH = textHeight + padding

      ctx.fillStyle = style.backgroundColor
      ctx.beginPath()
      ctx.roundRect(bgX, bgY, bgW, bgH, 8 * scale)
      ctx.fill()
    }

    // Text setup
    ctx.font = font
    ctx.textBaseline = 'top'

    const strokeW = (style.strokeWidth || 0) * scale

    let y = yBase + yOffset
    for (const line of layout.lines) {
      const x = w / 2

      if (style.preset === 'tiktok') {
        // === KARAOKE STYLE: word-by-word highlight with glow ===
        const lineWords = line.text.split(' ')
        let xOffset = x - line.width / 2
        ctx.textAlign = 'left'

        for (const lw of lineWords) {
          if (!lw) continue
          const isWordActive = chunkWords.some(
            cw => cw.word.toUpperCase() === lw && currentTime >= cw.start && currentTime <= cw.end
          )

          // Glow on active word
          if (isWordActive) {
            ctx.shadowColor = style.accentColor
            ctx.shadowBlur = 18 * scale
          } else {
            ctx.shadowColor = 'transparent'
            ctx.shadowBlur = 0
          }

          // Stroke
          if (strokeW > 0) {
            ctx.strokeStyle = style.outlineColor
            ctx.lineWidth = strokeW
            ctx.lineJoin = 'round'
            ctx.strokeText(lw, xOffset, y)
          }

          ctx.fillStyle = isWordActive ? style.accentColor : style.color
          ctx.fillText(lw, xOffset, y)

          // Underline active word
          if (isWordActive) {
            const wordWidth = ctx.measureText(lw).width
            ctx.fillStyle = style.accentColor
            ctx.globalAlpha = 0.8
            ctx.beginPath()
            ctx.roundRect(xOffset, y + fontSize + 2 * scale, wordWidth, 3 * scale, 2)
            ctx.fill()
            ctx.globalAlpha = fadeProgress
          }

          xOffset += ctx.measureText(lw + ' ').width
        }
        ctx.textAlign = 'center'

      } else if (style.preset === 'impact') {
        // === IMPACT STYLE: alternating colors + glow + big stroke ===
        const lineWords = line.text.split(' ')
        let xOffset = x - line.width / 2
        ctx.textAlign = 'left'

        // Background glow
        ctx.shadowColor = style.accentColor
        ctx.shadowBlur = 15 * scale

        const impactStroke = Math.max(strokeW, 3 * scale)
        lineWords.forEach((lw, idx) => {
          if (!lw) return

          // Stroke
          ctx.strokeStyle = style.outlineColor
          ctx.lineWidth = impactStroke
          ctx.lineJoin = 'round'
          ctx.strokeText(lw, xOffset, y)

          // Fill with alternating colors
          ctx.fillStyle = idx % 2 === 0 ? style.color : style.accentColor
          ctx.fillText(lw, xOffset, y)

          xOffset += ctx.measureText(lw + ' ').width
        })

        ctx.shadowBlur = 0
        ctx.textAlign = 'center'

      } else if (style.preset === 'karaoke') {
        // === KARAOKE STYLE: progressive fill per word ===
        const lineWords = line.text.split(' ')
        let xOffset = x - line.width / 2
        ctx.textAlign = 'left'

        for (const lw of lineWords) {
          if (!lw) continue
          const wordWidth = ctx.measureText(lw).width

          // Find matching word for timing
          const matchedWord = chunkWords.find(
            cw => cw.word.toUpperCase() === lw
          )
          const isWordActive = matchedWord && currentTime >= matchedWord.start && currentTime <= matchedWord.end
          const isWordPast = matchedWord && currentTime > matchedWord.end

          // Stroke
          if (strokeW > 0) {
            ctx.strokeStyle = style.outlineColor
            ctx.lineWidth = strokeW
            ctx.lineJoin = 'round'
            ctx.strokeText(lw, xOffset, y)
          }

          if (isWordActive && matchedWord) {
            // Progressive fill: base color → accent color sweep
            const wordProgress = Math.min(1, Math.max(0,
              (currentTime - matchedWord.start) / (matchedWord.end - matchedWord.start)
            ))
            const fillX = xOffset + wordWidth * wordProgress

            // Draw base color (unfilled part)
            ctx.save()
            ctx.beginPath()
            ctx.rect(fillX, y - fontSize, wordWidth - (fillX - xOffset) + 2, fontSize * 2)
            ctx.clip()
            ctx.fillStyle = style.color
            ctx.globalAlpha = fadeProgress * 0.5
            ctx.fillText(lw, xOffset, y)
            ctx.restore()

            // Draw accent color (filled part)
            ctx.save()
            ctx.beginPath()
            ctx.rect(xOffset - 1, y - fontSize, fillX - xOffset + 1, fontSize * 2)
            ctx.clip()
            ctx.shadowColor = style.accentColor
            ctx.shadowBlur = 10 * scale
            ctx.fillStyle = style.accentColor
            ctx.globalAlpha = fadeProgress
            ctx.fillText(lw, xOffset, y)
            ctx.restore()

            // Bounce on new word (first 100ms)
            if (matchedWord && currentTime - matchedWord.start < 0.1) {
              const bt = (currentTime - matchedWord.start) / 0.1
              const bounceScale = 1.05 - 0.05 * bt
              ctx.save()
              const cx = xOffset + wordWidth / 2
              const cy = y
              ctx.translate(cx, cy)
              ctx.scale(bounceScale, bounceScale)
              ctx.translate(-cx, -cy)
              ctx.restore()
            }
          } else {
            ctx.fillStyle = isWordPast ? style.accentColor : style.color
            ctx.globalAlpha = isWordPast ? fadeProgress : fadeProgress * 0.5
            ctx.fillText(lw, xOffset, y)
            ctx.globalAlpha = fadeProgress
          }

          xOffset += ctx.measureText(lw + ' ').width
        }
        ctx.textAlign = 'center'

      } else if (style.preset === 'boxed') {
        // === BOXED STYLE: individual rounded boxes per line with stagger reveal ===
        const chunkTime = chunkWords[0].start
        const elapsedSinceChunk = currentTime - chunkTime
        const lineIdx = layout.lines.indexOf(line)
        const lineDelay = lineIdx * 0.06 // 60ms stagger per line
        const boxTime = Math.max(0, elapsedSinceChunk - lineDelay)
        const boxProgress = Math.min(1, boxTime / 0.15) // 150ms to full width
        const textDelay = 0.03 // 30ms after box
        const textProgress = Math.min(1, Math.max(0, (boxTime - textDelay) / 0.12))

        const padding = 10 * scale
        const boxWidth = (line.width + padding * 2) * boxProgress
        const boxHeight = fontSize * 1.4
        const boxX = x - boxWidth / 2
        const boxY = y - fontSize * 0.15

        // Draw box
        ctx.save()
        const bgColor = style.backgroundColor !== 'transparent'
          ? style.backgroundColor
          : style.accentColor + '33' // fallback with alpha
        ctx.fillStyle = bgColor
        ctx.beginPath()
        ctx.roundRect(boxX, boxY, boxWidth, boxHeight, 6 * scale)
        ctx.fill()
        ctx.restore()

        // Draw text (appears after box)
        if (textProgress > 0) {
          ctx.save()
          ctx.globalAlpha = fadeProgress * textProgress
          ctx.textAlign = 'center'

          if (strokeW > 0) {
            ctx.strokeStyle = style.outlineColor
            ctx.lineWidth = strokeW
            ctx.lineJoin = 'round'
            ctx.strokeText(line.text, x, y)
          }

          ctx.fillStyle = style.color
          ctx.fillText(line.text, x, y)
          ctx.restore()
        }

      } else {
        // === MINIMAL STYLE ===
        ctx.textAlign = 'center'

        // Subtle glow
        if (strokeW > 0) {
          ctx.shadowColor = style.outlineColor
          ctx.shadowBlur = 8 * scale
          ctx.strokeStyle = style.outlineColor
          ctx.lineWidth = strokeW
          ctx.lineJoin = 'round'
          ctx.strokeText(line.text, x, y)
        }

        ctx.shadowColor = 'transparent'
        ctx.shadowBlur = 0
        ctx.fillStyle = style.color
        ctx.fillText(line.text, x, y)
      }

      y += lineHeight
    }

    ctx.restore()
  }, [composition, playerFrame, totalFrames])

  useEffect(() => {
    const tick = () => {
      draw()
      rafRef.current = requestAnimationFrame(tick)
    }
    tick()
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
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    />
  )
}
