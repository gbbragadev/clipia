'use client'

import { useEffect, useRef, useCallback } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

interface Particle {
  x: number
  y: number
  targetX: number
  targetY: number
  alpha: number
  vx: number
  vy: number
}

export default function PretextCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const particlesRef = useRef<Particle[]>([])
  const animRef = useRef<number>(0)
  const mouseRef = useRef({ x: -1000, y: -1000 })

  const initParticles = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr

    const font = '700 64px Inter, system-ui, sans-serif'
    const text = 'Auto Shorts'
    const prepared = prepareWithSegments(text, font)
    const result = layoutWithLines(prepared, rect.width - 40, 72)

    // Render text to offscreen canvas to sample pixel positions
    const offscreen = document.createElement('canvas')
    offscreen.width = rect.width
    offscreen.height = rect.height
    const offCtx = offscreen.getContext('2d')!
    offCtx.font = font
    offCtx.fillStyle = '#fff'
    offCtx.textBaseline = 'top'

    const lines = result.lines
    const startY = rect.height / 2 - (lines.length * 72) / 2
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const textWidth = offCtx.measureText(line.text).width
      const x = (rect.width - textWidth) / 2
      offCtx.fillText(line.text, x, startY + i * 72)
    }

    // Sample pixels
    const imageData = offCtx.getImageData(0, 0, rect.width, rect.height)
    const particles: Particle[] = []
    const step = 5

    for (let y = 0; y < rect.height; y += step) {
      for (let x = 0; x < rect.width; x += step) {
        const idx = (y * rect.width + x) * 4
        if (imageData.data[idx + 3] > 128) {
          particles.push({
            x: Math.random() * rect.width,
            y: Math.random() * rect.height,
            targetX: x,
            targetY: y,
            alpha: 0.3 + Math.random() * 0.7,
            vx: 0,
            vy: 0,
          })
        }
      }
    }
    particlesRef.current = particles
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top }
    }
    const handleMouseLeave = () => {
      mouseRef.current = { x: -1000, y: -1000 }
    }

    canvas.addEventListener('mousemove', handleMouseMove)
    canvas.addEventListener('mouseleave', handleMouseLeave)

    if (document.fonts?.ready) {
      document.fonts.ready.then(initParticles)
    } else {
      setTimeout(initParticles, 200)
    }

    const animate = () => {
      const ctx = canvas.getContext('2d')!
      const dpr = window.devicePixelRatio || 1
      const w = canvas.width / dpr
      const h = canvas.height / dpr

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      const mouse = mouseRef.current
      const particles = particlesRef.current

      for (const p of particles) {
        const dx = p.x - mouse.x
        const dy = p.y - mouse.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 80 && dist > 0) {
          const force = (80 - dist) / 80
          p.vx += (dx / dist) * force * 2
          p.vy += (dy / dist) * force * 2
        }

        p.vx += (p.targetX - p.x) * 0.05
        p.vy += (p.targetY - p.y) * 0.05
        p.vx *= 0.85
        p.vy *= 0.85
        p.x += p.vx
        p.y += p.vy

        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 2)
        gradient.addColorStop(0, `rgba(139, 92, 246, ${p.alpha})`)
        gradient.addColorStop(1, `rgba(59, 130, 246, ${p.alpha * 0.3})`)
        ctx.fillStyle = gradient
        ctx.beginPath()
        ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2)
        ctx.fill()
      }

      animRef.current = requestAnimationFrame(animate)
    }

    animate()

    const handleResize = () => initParticles()
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animRef.current)
      canvas.removeEventListener('mousemove', handleMouseMove)
      canvas.removeEventListener('mouseleave', handleMouseLeave)
      window.removeEventListener('resize', handleResize)
    }
  }, [initParticles])

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-[120px] md:h-[160px] cursor-crosshair"
      style={{ touchAction: 'none' }}
    />
  )
}
