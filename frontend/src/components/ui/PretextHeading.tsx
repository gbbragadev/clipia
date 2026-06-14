'use client'
import React, { useEffect, useRef, useState } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

interface PretextHeadingProps {
  text: string
  animation?: 'blur-focus' | 'pop' | 'typewriter' | 'karaoke'
  color?: string
  triggerOnView?: boolean
  className?: string
}

export function PretextHeading({
  text,
  animation = 'blur-focus',
  color = '#ffffff',
  triggerOnView = true,
  className = ''
}: PretextHeadingProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(!triggerOnView)
  const frameRef = useRef<number | undefined>(undefined)
  const startRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!triggerOnView) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.unobserve(entry.target)
        }
      },
      { threshold: 0.1 }
    )
    if (containerRef.current) {
      observer.observe(containerRef.current)
    }
    return () => observer.disconnect()
  }, [triggerOnView])

  useEffect(() => {
    if (!isVisible || !canvasRef.current || !containerRef.current) return
    let isActive = true
    const canvas = canvasRef.current
    const container = containerRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const render = (time: number) => {
      if (!isActive) return
      if (!startRef.current) startRef.current = time
      const elapsed = time - startRef.current

      const { width } = container.getBoundingClientRect()
      
      let fontSize = width < 400 ? 30 : width < 640 ? 38 : width < 768 ? 48 : 72
      const font = `900 ${fontSize}px Inter, sans-serif`
      const lineHeight = fontSize * 1.1

      canvas.width = width * window.devicePixelRatio
      canvas.height = (lineHeight * 3) * window.devicePixelRatio
      canvas.style.width = `${width}px`

      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const prepared = prepareWithSegments(text, font)
      const layoutResult = layoutWithLines(prepared, width, lineHeight)
      
      if (!layoutResult) return

      ctx.fillStyle = color
      ctx.font = font
      ctx.textBaseline = 'top'

      let y = 0
      const duration = 1500
      const progress = Math.min(elapsed / duration, 1)

      for (const line of layoutResult.lines) {
        const words = line.text.split(' ')
        let xOffset = 0
        for (let i = 0; i < words.length; i++) {
          const word = words[i]
          const wordWidth = ctx.measureText(word + ' ').width
          
          ctx.save()
          if (animation === 'blur-focus') {
            const wordDelay = i * 0.1
            const p = Math.max(0, Math.min((progress - wordDelay) / 0.5, 1))
            const eased = 1 - Math.pow(1 - p, 3)
            ctx.globalAlpha = eased
            ctx.filter = `blur(${(1 - eased) * 10}px)`
            ctx.fillText(word, xOffset, y)
          } else if (animation === 'pop') {
            const wordDelay = i * 0.1
            const p = Math.max(0, Math.min((progress - wordDelay) / 0.3, 1))
            const eased = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2
            
            ctx.translate(xOffset + wordWidth/2, y + fontSize/2)
            ctx.scale(eased, eased)
            ctx.translate(-(xOffset + wordWidth/2), -(y + fontSize/2))
            ctx.globalAlpha = p
            ctx.fillText(word, xOffset, y)
          } else {
            ctx.fillText(word, xOffset, y)
          }
          ctx.restore()
          
          xOffset += wordWidth
        }
        y += lineHeight
      }

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(render)
      }
    }

    document.fonts?.ready.then(() => {
      frameRef.current = requestAnimationFrame(render)
    })

    const handleResize = () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
      startRef.current = undefined
      frameRef.current = requestAnimationFrame(render)
    }
    
    window.addEventListener('resize', handleResize)
    return () => {
      isActive = false
      window.removeEventListener('resize', handleResize)
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
  }, [isVisible, text, animation, color])

  return (
    <div ref={containerRef} className={`w-full ${className}`}>
      <canvas ref={canvasRef} className="w-full block" />
    </div>
  )
}
