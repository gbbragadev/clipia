'use client'

import SocialProofCanvas from './SocialProofCanvas'

export default function SocialProofBar() {
  return (
    <div className="py-8 px-4">
      <div className="max-w-3xl mx-auto flex items-center justify-center gap-6 md:gap-12">
        <div className="text-center flex flex-col items-center">
          <SocialProofCanvas
            target={1000000}
            suffix="+"
            format={(n) =>
              n >= 1000000
                ? Math.floor(n / 1000000) + 'M+'
                : Math.floor(n / 1000) + 'K+'
            }
            gradientFrom="#c084fc"
            gradientTo="#f0abfc"
          />
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">views geradas</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center flex flex-col items-center">
          <SocialProofCanvas
            target={500}
            suffix="+"
            format={(n) => Math.floor(n) + '+'}
            gradientFrom="#60a5fa"
            gradientTo="#22d3ee"
          />
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">videos criados</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center flex flex-col items-center">
          <SocialProofCanvas
            target={45}
            suffix="s"
            format={(n) => Math.floor(n) + 's'}
            gradientFrom="#22d3ee"
            gradientTo="#4ade80"
          />
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">tempo medio</span>
        </div>
      </div>
    </div>
  )
}
