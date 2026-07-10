'use client'

/**
 * Stepper compacto das macro-etapas da geração — mata a sensação de "espera
 * morta": o usuário vê o vídeo ANDANDO pelas fases, não só um % opaco.
 * As etapas finas (STEP_LABELS) continuam como legenda; aqui é o mapa da viagem.
 */

const MACRO_STAGES = ['Roteiro', 'Áudio & mídia', 'Montagem', 'Final'] as const

/** Etapa fina (current_step do Redis) → índice da macro-etapa. */
const STEP_TO_STAGE: Record<string, number> = {
  scripting: 0,
  generating_images: 1,
  generating_videos: 1,
  tts: 1,
  transcribing: 1,
  media: 1,
  compositing: 2,
  preparing: 2,
  encoding: 2,
  finalizing: 3,
}

interface JobStepperProps {
  /** current_step vindo do Redis (null enquanto queued). */
  step: string | null | undefined
  /** true enquanto o job ainda está na fila (nenhuma etapa ativa). */
  queued: boolean
}

export default function JobStepper({ step, queued }: JobStepperProps) {
  const activeStage = queued ? -1 : (STEP_TO_STAGE[step ?? ''] ?? 0)

  return (
    <ol className="flex items-center gap-1" aria-label="Etapas da geração">
      {MACRO_STAGES.map((label, i) => {
        const done = i < activeStage
        const active = i === activeStage
        return (
          <li key={label} className="flex flex-1 items-center gap-1 min-w-0">
            <span
              aria-hidden
              className={`grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full text-[8px] font-bold transition-colors ${
                done
                  ? 'bg-mint/20 text-mint'
                  : active
                    ? 'bg-coral text-white animate-pulse'
                    : 'bg-white/10 text-transparent'
              }`}
            >
              {done ? '✓' : active ? '' : ''}
            </span>
            <span
              className={`truncate text-[9px] leading-none ${
                done ? 'text-mint/80' : active ? 'text-coral font-semibold' : 'text-slate-600'
              }`}
            >
              {label}
            </span>
            {i < MACRO_STAGES.length - 1 && (
              <span aria-hidden className={`h-px flex-1 min-w-1 ${done ? 'bg-mint/30' : 'bg-white/10'}`} />
            )}
          </li>
        )
      })}
    </ol>
  )
}
