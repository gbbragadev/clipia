'use client'

import { useEffect, useState } from 'react'

const scenes = [
  {
    title: '5 fatos sobre o oceano',
    gradient: 'from-blue-900 to-cyan-900',
    caption: 'Voce sabia que o oceano cobre 71% da Terra?',
  },
  {
    title: 'Por que gatos ronronam?',
    gradient: 'from-purple-900 to-fuchsia-900',
    caption: 'A ciencia por tras do ronronar felino',
  },
  {
    title: 'A historia do cafe',
    gradient: 'from-amber-900 to-orange-900',
    caption: 'Da Etiopia para o mundo em seculos',
  },
]

export default function PhoneMockup() {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrent(prev => (prev + 1) % scenes.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="relative flex items-center justify-center">
      {/* Glow orbs */}
      <div className="absolute -top-10 -left-10 w-40 h-40 bg-purple-500/20 rounded-full blur-3xl" />
      <div className="absolute -bottom-10 -right-10 w-32 h-32 bg-blue-500/20 rounded-full blur-3xl" />
      <div className="absolute top-1/2 right-0 w-24 h-24 bg-fuchsia-500/15 rounded-full blur-2xl" />

      {/* Phone frame */}
      <div className="relative w-[220px] md:w-[260px] rounded-[2.5rem] border-4 border-gray-700/50 bg-black overflow-hidden shadow-2xl"
           style={{ aspectRatio: '9/19.5' }}>
        {/* Notch */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2 w-20 h-5 bg-black rounded-full z-20" />

        {/* Scenes */}
        {scenes.map((scene, i) => (
          <div
            key={i}
            className={`absolute inset-0 flex flex-col justify-between p-4 pt-10 pb-6 transition-opacity duration-700 bg-gradient-to-b ${scene.gradient}`}
            style={{ opacity: current === i ? 1 : 0 }}
          >
            {/* Title */}
            <div className="flex-1 flex items-center justify-center px-2">
              <h3 className="text-white text-lg md:text-xl font-bold text-center leading-tight drop-shadow-lg">
                {scene.title}
              </h3>
            </div>

            {/* Social icons on the right */}
            <div className="absolute right-3 bottom-24 flex flex-col items-center gap-4">
              {/* Heart */}
              <div className="flex flex-col items-center gap-1">
                <div className="w-7 h-7 flex items-center justify-center">
                  <div className="w-3 h-3 bg-red-500 rounded-full relative">
                    <div className="absolute -left-1.5 top-0 w-3 h-3 bg-red-500 rounded-full" />
                    <div className="absolute left-0 top-1.5 w-3 h-3 bg-red-500 rotate-45" />
                  </div>
                </div>
                <span className="text-white text-[10px]">12.4K</span>
              </div>
              {/* Comment */}
              <div className="flex flex-col items-center gap-1">
                <div className="w-5 h-5 rounded-full border-2 border-white/70" />
                <span className="text-white text-[10px]">342</span>
              </div>
              {/* Share */}
              <div className="flex flex-col items-center gap-1">
                <div className="w-0 h-0 border-l-[8px] border-l-transparent border-r-[8px] border-r-transparent border-b-[12px] border-b-white/70 rotate-90" />
                <span className="text-white text-[10px]">89</span>
              </div>
            </div>

            {/* Caption */}
            <div className="mt-auto">
              <p className="text-white/80 text-xs leading-relaxed">{scene.caption}</p>
            </div>

            {/* Progress bar */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20">
              <div
                className="h-full bg-white/80 transition-all duration-[3000ms] ease-linear"
                style={{ width: current === i ? '100%' : '0%' }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
