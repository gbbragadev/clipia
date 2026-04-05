'use client'

import SocialProofCanvas from './SocialProofCanvas'

export default function SocialProofBar() {
  return (
    <div className="py-8 px-4">
      <div className="max-w-3xl mx-auto flex items-center justify-center gap-6 md:gap-12">
        <div className="text-center flex flex-col items-center">
          <SocialProofCanvas
            target={500}
            suffix="+"
            format={(n) => Math.floor(n) + '+'}
            gradientFrom="#c084fc"
            gradientTo="#f0abfc"
          />
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">vídeos criados</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center flex flex-col items-center">
          <SocialProofCanvas
            target={2}
            suffix="min"
            format={(n) => Math.floor(n) + 'min'}
            gradientFrom="#60a5fa"
            gradientTo="#22d3ee"
          />
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">tempo médio</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center flex flex-col items-center">
          <SocialProofCanvas
            target={3}
            suffix=""
            format={(n) => Math.floor(n) + ''}
            gradientFrom="#22d3ee"
            gradientTo="#4ade80"
          />
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">vozes pt-BR</span>
        </div>
      </div>
    </div>
  )
}
