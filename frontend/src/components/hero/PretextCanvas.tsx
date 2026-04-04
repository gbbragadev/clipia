'use client'

import { useEffect, useRef } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

const PHRASES = [
  'Voce sabia que o oceano cobre mais de 70% da Terra?',
  'O cafe foi descoberto na Etiopia no seculo IX.',
  'Gatos ronronam entre 25 e 150 hertz de frequencia.',
  'O Sol tem 4.6 bilhoes de anos de idade.',
]

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

    const font = '600 15px Inter, system-ui, sans-serif'
    let startTime = Date.now()
    let phraseIdx = 0

    const animate = () => {
      const elapsed = Date.now() - startTime
      const w = rect.width
      const h = rect.height

      ctx.clearRect(0, 0, w, h)

      const phrase = PHRASES[phraseIdx]
      const prepared = prepareWithSegments(phrase, font)
      const result = layoutWithLines(prepared, w - 24, 22)

      const words = phrase.split(' ')
      const totalDur = 3000
      const wordsVisible = Math.floor((elapsed / totalDur) * words.length * 1.5)

      let wordIdx = 0
      let yOff = 8
      for (const line of result.lines) {
        const lineWords = line.text.split(' ')
        let xOff = 12

        for (const word of lineWords) {
          if (!word) continue
          const show = wordIdx < wordsVisible

          if (show) {
            const isHighlighted = wordIdx === wordsVisible - 1
            ctx.font = font

            if (isHighlighted) {
              const metrics = ctx.measureText(word)
              ctx.fillStyle = 'rgba(124, 58, 237, 0.4)'
              ctx.beginPath()
              ctx.roundRect(xOff - 3, yOff, metrics.width + 6, 20, 4)
              ctx.fill()
              ctx.fillStyle = 'rgba(255, 255, 255, 1)'
            } else {
              ctx.fillStyle = 'rgba(255, 255, 255, 0.7)'
            }

            ctx.fillText(word, xOff, yOff + 15)
          }

          ctx.font = font
          const metrics = ctx.measureText(word + ' ')
          xOff += metrics.width
          wordIdx++
        }
        yOff += 22
      }

      if (elapsed > totalDur + 800) {
        phraseIdx = (phraseIdx + 1) % PHRASES.length
        startTime = Date.now()
      }

      animRef.current = requestAnimationFrame(animate)
    }

    const init = () => animate()
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
        style={{ width: '100%', height: 72, display: 'block' }}
      />
    </div>
  )
}
