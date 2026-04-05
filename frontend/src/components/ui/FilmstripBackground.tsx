'use client'
import React from 'react'

export function FilmstripBackground({ speed = 20, opacity = 0.03 }) {
  return (
    <div className="absolute inset-0 z-[-1] overflow-hidden pointer-events-none" style={{ opacity }}>
      <div 
        className="absolute top-0 bottom-0 left-0 w-8 flex flex-col items-center justify-around py-4 border-r border-white/20"
        style={{ animation: `slideUp ${speed}s linear infinite` }}
      >
        {Array.from({ length: 20 }).map((_, i) => (
          <div key={i} className="w-4 h-3 bg-white/40 rounded-sm mb-4" />
        ))}
      </div>
      <div 
        className="absolute top-0 bottom-0 right-0 w-8 flex flex-col items-center justify-around py-4 border-l border-white/20"
        style={{ animation: `slideUp ${speed}s linear infinite` }}
      >
        {Array.from({ length: 20 }).map((_, i) => (
          <div key={i} className="w-4 h-3 bg-white/40 rounded-sm mb-4" />
        ))}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideUp {
          from { transform: translateY(0); }
          to { transform: translateY(-50%); }
        }
      `}} />
    </div>
  )
}
