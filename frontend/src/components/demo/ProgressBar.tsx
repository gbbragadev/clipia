'use client'

import { strings } from '@/lib/strings';

const STEPS = [
  { key: 'scripting', label: 'Roteiro' },
  { key: 'tts', label: 'Narracao' },
  { key: 'transcribing', label: strings.editor.subtitles },
  { key: 'media', label: 'Midia' },
  { key: 'compositing', label: 'Montagem' },
  { key: 'finalizing', label: 'Final' },
]

interface Props {
  progress: number
  currentStep: string | null
  stepLabel: string | null
}

export default function ProgressBar({ progress, currentStep, stepLabel }: Props) {
  const currentIdx = STEPS.findIndex(s => s.key === currentStep)

  return (
    <div className="space-y-4 mt-6">
      <div className="flex justify-between text-sm text-gray-400">
        <span>{stepLabel || 'Aguardando...'}</span>
        <span className="font-mono tabular-nums">{Math.round(progress * 100)}%</span>
      </div>

      {/* Timeline track */}
      <div className="relative">
        {/* Connecting lines */}
        <div className="absolute top-3 left-3 right-3 h-0.5 bg-white/10" />

        {/* Progress fill line */}
        <div
          className="absolute top-3 left-3 h-0.5 bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
          style={{ width: `${Math.min(progress * 100, 100)}%`, maxWidth: 'calc(100% - 24px)' }}
        />

        {/* Step circles */}
        <div className="relative flex justify-between">
          {STEPS.map((step, idx) => {
            const isDone = currentIdx > idx
            const isActive = step.key === currentStep

            return (
              <div key={step.key} className="flex flex-col items-center gap-1.5">
                <div className="relative">
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                      isDone
                        ? 'border-purple-500 bg-purple-500'
                        : isActive
                        ? 'border-purple-400 bg-transparent'
                        : 'border-gray-700 bg-transparent'
                    } ${isActive ? 'shadow-[0_0_12px_rgba(139,92,246,0.5)]' : ''}`}
                  >
                    {isDone && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                    {isActive && (
                      <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                    )}
                  </div>
                  {/* Diamond scrubber on active */}
                  {isActive && (
                    <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-2 h-2 bg-purple-400 rotate-45" />
                  )}
                </div>
                <span className={`text-[10px] md:text-xs transition-colors ${
                  isDone ? 'text-purple-300' :
                  isActive ? 'text-white' :
                  'text-gray-600'
                }`}>
                  {step.label}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
