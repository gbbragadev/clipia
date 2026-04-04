'use client'

import { useInView } from '@/hooks/useInView'
import { useCountUp } from '@/hooks/useCountUp'

export default function SocialProofBar() {
  const { ref, inView } = useInView(0.3)

  const views = useCountUp(1000000, 2000, inView)
  const videos = useCountUp(500, 1800, inView)
  const seconds = useCountUp(45, 1500, inView)

  const formatViews = (n: number) => {
    if (n >= 1000000) return '1M+'
    if (n >= 1000) return `${Math.round(n / 1000)}K+`
    return `${n}+`
  }

  return (
    <div ref={ref} className="py-10 px-4">
      <div className="max-w-3xl mx-auto flex items-center justify-center gap-6 md:gap-12">
        <div className="text-center">
          <span className="block text-2xl md:text-3xl font-bold font-mono tabular-nums bg-gradient-to-r from-purple-400 to-fuchsia-400 bg-clip-text text-transparent">
            {formatViews(views)}
          </span>
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">views geradas</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center">
          <span className="block text-2xl md:text-3xl font-bold font-mono tabular-nums bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            {videos}+
          </span>
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">videos criados</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center">
          <span className="block text-2xl md:text-3xl font-bold font-mono tabular-nums bg-gradient-to-r from-cyan-400 to-green-400 bg-clip-text text-transparent">
            {seconds}s
          </span>
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">tempo medio</span>
        </div>
      </div>
    </div>
  )
}
