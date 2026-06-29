'use client'

import { useEffect, useRef } from 'react'
import {
  prepareWithSegments,
  layoutWithLines,
  layoutNextLine,
  type PreparedTextWithSegments,
  type LayoutCursor,
} from '@chenglou/pretext'
import { prefersReducedMotion } from '@/lib/motion'

const PHRASES = [
  'Voce sabia que o oceano cobre mais de 70% da Terra?',
  'O cafe foi descoberto na Etiopia no seculo IX.',
  'Gatos ronronam entre 25 e 150 hertz de frequencia.',
  'O Sol tem 4.6 bilhoes de anos de idade.',
]

const MODES = ['karaoke', 'typewriter', 'blur', 'pop'] as const
type AnimMode = (typeof MODES)[number]

const MODE_LABELS: Record<AnimMode, string> = {
  karaoke: 'karaoke sweep',
  typewriter: 'typewriter',
  blur: 'blur → focus',
  pop: 'scale pop',
}

const PHRASE_DURATION = 3200
const PAUSE_BETWEEN = 600

export default function PretextCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr

    const ctx = canvas.getContext('2d')!
    ctx.scale(dpr, dpr)

    const fontPx = rect.width < 640 ? 12 : rect.width < 768 ? 14 : 15
    const font = `600 ${fontPx}px Inter, system-ui, sans-serif`
    const labelFont = '500 9px Inter, system-ui, sans-serif'
    let startTime = Date.now()
    let phraseIdx = 0

    const animate = () => {
      const elapsed = Date.now() - startTime
      const w = rect.width
      const h = rect.height
      const textAreaH = h - 18 // reserve 18px for label

      ctx.clearRect(0, 0, w, h)

      const phrase = PHRASES[phraseIdx]
      const mode = MODES[phraseIdx % MODES.length]
      const prepared = prepareWithSegments(phrase, font)
      const result = layoutWithLines(prepared, Math.max(100, w - 24), 22)

      const words = phrase.split(' ')
      const progress = Math.min(1, elapsed / PHRASE_DURATION)

      // Draw text based on mode
      drawMode(ctx, mode, prepared, result, words, progress, elapsed, w, textAreaH, font)

      // Draw mode label
      drawLabel(ctx, mode, w, h, labelFont, elapsed)

      if (elapsed > PHRASE_DURATION + PAUSE_BETWEEN) {
        phraseIdx = (phraseIdx + 1) % PHRASES.length
        startTime = Date.now()
      }

      animRef.current = requestAnimationFrame(animate)
    }

    const init = () => {
      // a11y: sem ciclo de frases nem rAF — desenha uma frase completa, legivel e parada.
      if (prefersReducedMotion()) {
        const w = rect.width
        const h = rect.height
        const phrase = PHRASES[0]
        ctx.clearRect(0, 0, w, h)
        const prepared = prepareWithSegments(phrase, font)
        const result = layoutWithLines(prepared, Math.max(100, w - 24), 22)
        drawMode(ctx, 'blur', prepared, result, phrase.split(' '), 1, 99999, w, h - 18, font)
        return
      }
      animate()
    }
    if (document.fonts?.ready) {
      document.fonts.ready.then(init)
    } else {
      setTimeout(init, 200)
    }

    return () => cancelAnimationFrame(animRef.current)
  }, [])

  return (
    <div style={{
      borderRadius: 12,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)',
      overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <span style={{ fontSize: 10, color: '#7c3aed', fontWeight: 600, letterSpacing: '0.05em' }}>LEGENDAS AO VIVO</span>
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#22c55e', animation: 'pulse-glow 1.5s infinite' }} />
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: 90, display: 'block' }}
      />
    </div>
  )
}

// ── Mode: Karaoke Sweep ──
// Gradient fill travels left→right across each word
function drawKaraoke(
  ctx: CanvasRenderingContext2D,
  prepared: PreparedTextWithSegments,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  progress: number,
  w: number,
  h: number,
  font: string,
) {
  const wordsVisible = Math.floor(progress * words.length * 1.4)
  const activeWordIdx = Math.min(wordsVisible - 1, words.length - 1)

  // Per-word progress for active word
  const wordSlotDuration = 1 / (words.length * 1.4)
  const activeWordStart = activeWordIdx * wordSlotDuration
  const fillProgress = Math.min(1, Math.max(0, (progress - activeWordStart) / wordSlotDuration))

  let wordIdx = 0
  let yOff = 8
  ctx.font = font

  for (const line of result.lines) {
    const lineWords = line.text.split(' ')
    let xOff = 12

    for (const word of lineWords) {
      if (!word) continue
      const show = wordIdx <= activeWordIdx && wordIdx < wordsVisible

      if (show) {
        const wordWidth = ctx.measureText(word).width

        if (wordIdx === activeWordIdx) {
          // Active word: gradient fill sweep
          const grad = ctx.createLinearGradient(xOff, 0, xOff + wordWidth, 0)
          grad.addColorStop(0, 'rgba(167, 139, 250, 1)')
          grad.addColorStop(Math.min(1, fillProgress), 'rgba(167, 139, 250, 1)')
          grad.addColorStop(Math.min(1, fillProgress + 0.01), 'rgba(255, 255, 255, 0.5)')
          grad.addColorStop(1, 'rgba(255, 255, 255, 0.5)')
          ctx.fillStyle = grad
          ctx.fillText(word, xOff, yOff + 15)

          // Underline sweep
          ctx.fillStyle = 'rgba(167, 139, 250, 0.6)'
          ctx.fillRect(xOff, yOff + 18, wordWidth * fillProgress, 2)
        } else {
          // Past word: solid
          ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
          ctx.fillText(word, xOff, yOff + 15)
        }
      }

      const metrics = ctx.measureText(word + ' ')
      xOff += metrics.width
      wordIdx++
    }
    yOff += 22
  }
}

// ── Mode: Typewriter ──
// Character-by-character reveal with blinking cursor
function drawTypewriter(
  ctx: CanvasRenderingContext2D,
  prepared: PreparedTextWithSegments,
  result: ReturnType<typeof layoutWithLines>,
  progress: number,
  elapsed: number,
  w: number,
  h: number,
  font: string,
) {
  // Use layoutNextLine iterator for line-by-line reveal
  const fullText = result.lines.map(l => l.text).join('')
  const totalChars = fullText.length
  const charsVisible = Math.floor(progress * totalChars * 1.3)

  let charCount = 0
  let yOff = 8
  let cursorX = 12
  let cursorY = yOff + 15
  ctx.font = font

  const cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 }
  let line = layoutNextLine(prepared, cursor, w - 24)

  while (line) {
    const lineChars = line.text.length
    const visibleInLine = Math.min(lineChars, Math.max(0, charsVisible - charCount))

    if (visibleInLine > 0) {
      const visibleText = line.text.substring(0, visibleInLine)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.fillText(visibleText, 12, yOff + 15)

      // Track cursor position
      cursorX = 12 + ctx.measureText(visibleText).width
      cursorY = yOff + 15
    }

    charCount += lineChars
    if (charCount >= charsVisible) break

    yOff += 22
    line = layoutNextLine(prepared, line.end, w - 24)
  }

  // Blinking cursor
  const blink = Math.floor(elapsed / 400) % 2 === 0
  if (blink && progress < 0.95) {
    ctx.fillStyle = 'rgba(167, 139, 250, 0.9)'
    ctx.fillRect(cursorX + 1, cursorY - 12, 2, 14)
  }
}

// ── Mode: Blur-to-Focus ──
// Words start blurred, each sharpens as it becomes active
function drawBlurToFocus(
  ctx: CanvasRenderingContext2D,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  progress: number,
  w: number,
  h: number,
  font: string,
) {
  const wordsVisible = Math.floor(progress * words.length * 1.4)

  let wordIdx = 0
  let yOff = 8
  ctx.font = font

  for (const line of result.lines) {
    const lineWords = line.text.split(' ')
    let xOff = 12

    for (const word of lineWords) {
      if (!word) continue

      const isFocused = wordIdx < wordsVisible
      const isActive = wordIdx === wordsVisible - 1

      // Save for per-word filter
      ctx.save()

      if (!isFocused) {
        ctx.filter = 'blur(4px)'
        ctx.globalAlpha = 0.25
      } else if (isActive) {
        // Transitioning from blur to focus
        const wordSlot = 1 / (words.length * 1.4)
        const wordStart = wordIdx * wordSlot
        const t = Math.min(1, (progress - wordStart) / wordSlot)
        const blur = Math.max(0, 4 * (1 - t))
        ctx.filter = blur > 0.1 ? `blur(${blur.toFixed(1)}px)` : 'none'
        ctx.globalAlpha = 0.5 + 0.5 * t
      } else {
        ctx.filter = 'none'
        ctx.globalAlpha = 1
      }

      ctx.fillStyle = isActive ? 'rgba(167, 139, 250, 1)' : 'rgba(255, 255, 255, 0.9)'
      ctx.fillText(word, xOff, yOff + 15)
      ctx.restore()

      const metrics = ctx.measureText(word + ' ')
      xOff += metrics.width
      wordIdx++
    }
    yOff += 22
  }
}

// ── Mode: Scale Pop ──
// Each word pops in with scale 1.2→1.0 + fade
function drawScalePop(
  ctx: CanvasRenderingContext2D,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  progress: number,
  w: number,
  h: number,
  font: string,
) {
  const wordsVisible = Math.floor(progress * words.length * 1.4)

  let wordIdx = 0
  let yOff = 8
  ctx.font = font

  for (const line of result.lines) {
    const lineWords = line.text.split(' ')
    let xOff = 12

    for (const word of lineWords) {
      if (!word) continue
      const show = wordIdx < wordsVisible
      const isActive = wordIdx === wordsVisible - 1

      if (show) {
        const wordWidth = ctx.measureText(word).width

        if (isActive) {
          const wordSlot = 1 / (words.length * 1.4)
          const wordStart = wordIdx * wordSlot
          const t = Math.min(1, (progress - wordStart) / wordSlot)
          // Elastic ease-out
          const ease = t < 1 ? 1 - Math.pow(2, -10 * t) : 1
          const scale = 1.25 - 0.25 * ease

          ctx.save()
          const cx = xOff + wordWidth / 2
          const cy = yOff + 10
          ctx.translate(cx, cy)
          ctx.scale(scale, scale)
          ctx.translate(-cx, -cy)
          ctx.globalAlpha = ease

          // Glow on active
          ctx.shadowColor = 'rgba(167, 139, 250, 0.6)'
          ctx.shadowBlur = 12 * (1 - ease) + 2

          ctx.fillStyle = 'rgba(167, 139, 250, 1)'
          ctx.fillText(word, xOff, yOff + 15)
          ctx.restore()
        } else {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
          ctx.fillText(word, xOff, yOff + 15)
        }
      }

      const metrics = ctx.measureText(word + ' ')
      xOff += metrics.width
      wordIdx++
    }
    yOff += 22
  }
}

// ── Dispatcher ──
function drawMode(
  ctx: CanvasRenderingContext2D,
  mode: AnimMode,
  prepared: PreparedTextWithSegments,
  result: ReturnType<typeof layoutWithLines>,
  words: string[],
  progress: number,
  elapsed: number,
  w: number,
  h: number,
  font: string,
) {
  switch (mode) {
    case 'karaoke':
      drawKaraoke(ctx, prepared, result, words, progress, w, h, font)
      break
    case 'typewriter':
      drawTypewriter(ctx, prepared, result, progress, elapsed, w, h, font)
      break
    case 'blur':
      drawBlurToFocus(ctx, result, words, progress, w, h, font)
      break
    case 'pop':
      drawScalePop(ctx, result, words, progress, w, h, font)
      break
  }
}

// ── Mode Label ──
function drawLabel(
  ctx: CanvasRenderingContext2D,
  mode: AnimMode,
  w: number,
  h: number,
  font: string,
  elapsed: number,
) {
  const label = MODE_LABELS[mode]
  const fadeIn = Math.min(1, elapsed / 400)
  const fadeOut = elapsed > PHRASE_DURATION ? Math.max(0, 1 - (elapsed - PHRASE_DURATION) / 300) : 1
  const alpha = fadeIn * fadeOut

  ctx.save()
  ctx.globalAlpha = alpha * 0.5
  ctx.font = font
  ctx.fillStyle = 'rgba(167, 139, 250, 1)'
  ctx.textAlign = 'right'
  ctx.fillText(label, w - 12, h - 6)
  ctx.textAlign = 'left'
  ctx.restore()
}
