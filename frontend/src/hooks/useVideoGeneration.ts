'use client'

import { useCallback, useRef, useState } from 'react'
import { generateVideo, getJobStatus, getDownloadUrl, type GenerateRequest, type JobStatus } from '@/lib/api'

const STEP_LABELS: Record<string, string> = {
  scripting: 'Gerando roteiro...',
  tts: 'Narrando com IA...',
  transcribing: 'Criando legendas...',
  media: 'Buscando midia...',
  compositing: 'Montando video...',
  finalizing: 'Finalizando...',
}

export function useVideoGeneration() {
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const generate = useCallback(async (req: GenerateRequest) => {
    setIsGenerating(true)
    setError(null)
    setStatus(null)
    setDownloadUrl(null)
    stopPolling()

    try {
      const { job_id } = await generateVideo(req)

      pollRef.current = setInterval(async () => {
        try {
          const job = await getJobStatus(job_id)
          setStatus(job)

          if (job.status === 'completed') {
            stopPolling()
            setIsGenerating(false)
            setDownloadUrl(getDownloadUrl(job_id))
          } else if (job.status === 'failed') {
            stopPolling()
            setIsGenerating(false)
            setError(job.error || 'Falha na geracao do video')
          }
        } catch {
          stopPolling()
          setIsGenerating(false)
          setError('Erro ao verificar status')
        }
      }, 2000)
    } catch {
      setIsGenerating(false)
      setError('Erro ao iniciar geracao')
    }
  }, [stopPolling])

  const stepLabel = status?.current_step ? STEP_LABELS[status.current_step] || status.current_step : null

  return { generate, status, isGenerating, error, downloadUrl, stepLabel }
}
