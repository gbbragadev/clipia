'use client'

import { useVideoGeneration } from '@/hooks/useVideoGeneration'
import GenerateForm from './GenerateForm'
import ProgressBar from './ProgressBar'
import VideoPlayer from './VideoPlayer'

export default function DemoSection() {
  const { generate, status, isGenerating, error, downloadUrl, stepLabel } = useVideoGeneration()

  return (
    <section id="demo" className="py-20 px-4">
      <div className="max-w-lg mx-auto">
        <h2 className="text-sm font-mono text-gray-500 text-center mb-2 tracking-wider">
          Cena 02 &middot; 00:42
        </h2>
        <h3 className="text-2xl font-bold text-center mb-2">Experimente agora</h3>
        <p className="text-gray-400 text-center mb-8">
          Digite um tema e veja a IA criar seu video em minutos.
        </p>

        {/* Editor window chrome */}
        <div className="rounded-2xl bg-[#0a0a14] border border-gray-800 overflow-hidden">
          {/* Title bar */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800/50 bg-[#08080f]">
            <div className="w-3 h-3 rounded-full bg-red-500/70" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
            <span className="ml-3 text-xs text-gray-500 font-mono">ClipIA Editor</span>
          </div>

          {/* Content */}
          <div className="p-6">
            <GenerateForm
              onGenerate={(topic, style, duration) =>
                generate({ topic, style, duration_target: duration })
              }
              isGenerating={isGenerating}
            />

            {(isGenerating || status) && !downloadUrl && !error && (
              <ProgressBar
                progress={status?.progress || 0}
                currentStep={status?.current_step || null}
                stepLabel={stepLabel}
              />
            )}

            {error && (
              <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            {downloadUrl && <VideoPlayer downloadUrl={downloadUrl} />}
          </div>
        </div>
      </div>
    </section>
  )
}
