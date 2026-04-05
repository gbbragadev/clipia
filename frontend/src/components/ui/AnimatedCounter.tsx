'use client'
import React, { useEffect, useRef, useState } from 'react'
import { prepareWithSegments, layout } from '@chenglou/pretext'

interface AnimatedCounterProps {
  value: number
  suffix?: string
  label?: string
  className?: string
}

export function AnimatedCounter({ value, suffix = '', label, className = '' }: AnimatedCounterProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isVisible, setIsVisible] = useState(false)
  
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.unobserve(entry.target)
        }
      },
      { threshold: 0.1 }
    )
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!isVisible || !canvasRef.current || !containerRef.current) return
    let isActive = true
    const canvas = canvasRef.current
    const container = containerRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let start: number | undefined
    const duration = 2000

    const render = (time: number) => {
      if (!isActive) return
      if (!start) start = time
      const elapsed = time - start
      const progress = Math.min(elapsed / duration, 1)
      
      const p = progress < 0.5 
        ? 8 * progress * progress * progress * progress 
        : 1 - Math.pow(-2 * progress + 2, 4) / 2

      const currentVal = Math.floor(p * value)
      const text = `${currentVal}${suffix}`

      const { width } = container.getBoundingClientRect()
      
      let lo = 10, hi = 200
      let fontName = 'Inter, sans-serif'
      while (hi - lo > 0.5) {
        const mid = (lo + hi) / 2
        const font = `900 ${mid}px ${fontName}`
        const prepared = prepareWithSegments(text, font)
        const result = layout(prepared, width, mid * 1.1)
        if (result && result.lineCount <= 1) lo = mid
        else hi = mid
      }
      
      const fontSize = lo
      const font = `900 ${fontSize}px ${fontName}`
      const lineHeight = fontSize * 1.1

      canvas.width = width * window.devicePixelRatio
      canvas.height = lineHeight * window.devicePixelRatio
      canvas.style.width = `${width}px`
      canvas.style.height = `${lineHeight}px`

      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      
      ctx.fillStyle = '#ffffff'
      ctx.font = font
      ctx.textBaseline = 'top'
      ctx.textAlign = 'center'
      ctx.fillText(text, width / 2, 0)

      if (progress < 1) {
        requestAnimationFrame(render)
      } else {
        const finalFont = `900 ${fontSize}px ${fontName}`
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.font = finalFont
        ctx.fillText(`${value}${suffix}`, width / 2, 0)
      }
    }

    document.fonts?.ready.then(() => {
      requestAnimationFrame(render)
    })

    return () => { isActive = false }
  }, [isVisible, value, suffix])

  return (
    <div ref={containerRef} className={`w-full flex flex-col items-center justify-center ${className}`}>
      <canvas ref={canvasRef} className="w-full block mb-4" />
      {label && (
        <p className="text-xl md:text-2xl font-medium text-slate-400 uppercase tracking-widest">{label}</p>
      )}
    </div>
  )
}
