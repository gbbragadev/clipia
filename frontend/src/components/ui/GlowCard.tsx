'use client'
import React, { useRef, useState } from 'react'

interface GlowCardProps {
  children: React.ReactNode
  glowColor?: string
  intensity?: number
  className?: string
}

export function GlowCard({
  children,
  glowColor = '#ff5638',
  intensity = 0.3,
  className = ''
}: GlowCardProps) {
  const divRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [opacity, setOpacity] = useState(0)

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return
    const rect = divRef.current.getBoundingClientRect()
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(intensity)}
      onMouseLeave={() => setOpacity(0)}
      className={`relative overflow-hidden rounded-2xl bg-[#16161d]/80 backdrop-blur-sm border border-white/5 transition-colors duration-300 hover:border-white/10 ${className}`}
    >
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, ${glowColor}30, transparent 40%)`
        }}
      />
      <div className="relative z-10 h-full w-full">
        {children}
      </div>
    </div>
  )
}
