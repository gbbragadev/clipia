'use client'
import { useEffect, useRef } from 'react'

export default function FilmGrain() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    canvas.width = 128
    canvas.height = 128
    // Grain ESTÁTICO: regenerar a 150ms custava CPU contínua em toda rota e, a 4%
    // de opacidade sob mix-blend-overlay, a animação era imperceptível.
    const img = ctx.createImageData(128, 128)
    for (let i = 0; i < img.data.length; i += 4) {
      const v = Math.random() * 255
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v
      img.data[i + 3] = 15
    }
    ctx.putImageData(img, 0, 0)
  }, [])
  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-50 h-full w-full opacity-[0.04] mix-blend-overlay"
      style={{ imageRendering: 'pixelated' }}
    />
  )
}
