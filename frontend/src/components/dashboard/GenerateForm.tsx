'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import {
  generateVideo,
  fetchJobStatus,
  type GenerateParams,
  type JobStatusResponse,
} from '@/lib/editor-api'
import TemplateSelector from './TemplateSelector'
import StyleSelector, { type StyleValue } from './StyleSelector'

const STEP_LABELS: Record<string, string> = {
  scripting: 'Escrevendo roteiro...',
  tts: 'Gerando narração...',
  transcribing: 'Transcrevendo áudio...',
  media: 'Buscando vídeos...',
  compositing: 'Montando vídeo...',
  finalizing: 'Finalizando...',
}

interface GenerateFormProps {
  onJobComplete: () => void
}

export default function GenerateForm({ onJobComplete }: GenerateFormProps) {
  const { user, refreshUser } = useAuth()

  const [topic, setTopic] = useState('')
  const [style, setStyle] = useState<StyleValue>('educational')
  const [templateId, setTemplateId] = useState('stock_narration')
  const [duration, setDuration] = useState(30)
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<JobStatusResponse | null>(null)
  const [showCreditsModal, setShowCreditsModal] = useState(false)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Poll active job
  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchJobStatus(jobId)
        setActiveJob(status)
        if (status.status === 'completed' || status.status === 'editable') {
          if (pollRef.current) clearInterval(pollRef.current)
          setGenerating(false)
          onJobComplete()
          refreshUser()
        } else if (status.status === 'failed' || status.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          setGenerating(false)
          setGenError(status.error || 'Erro ao gerar vídeo')
          onJobComplete()
        }
      } catch { /* silent */ }
    }, 2000)
  }, [onJobComplete])

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const handleGenerate = async () => {
    if (!topic.trim() || generating) return

    if (user && user.credits <= 0) {
      setShowCreditsModal(true)
      return
    }

    setGenerating(true)
    setGenError(null)
    setActiveJob(null)
    try {
      const params: GenerateParams = {
        topic: topic.trim(),
        style,
        duration_target: duration,
        template_id: templateId,
      }
      const result = await generateVideo(params)
      startPolling(result.job_id)
      setActiveJob({
        job_id: result.job_id,
        status: 'queued',
        progress: 0,
        current_step: null,
        error: null,
        created_at: new Date().toISOString(),
        download_url: null,
      })
    } catch (err) {
      setGenerating(false)
      setGenError(err instanceof Error ? err.message : 'Erro ao iniciar geração')
    }
  }

  return (
    <section>
      <h2 className="text-xl font-bold mb-6">Criar novo vídeo</h2>

      {/* Template */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-2">Template</label>
        <TemplateSelector selected={templateId} onSelect={setTemplateId} disabled={generating} />
      </div>

      {/* Topic */}
      <div className="mb-4">
        <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">Tema do vídeo</label>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate() }}
          placeholder="Ex: 5 curiosidades sobre o oceano profundo"
          disabled={generating}
          className="w-full px-4 py-3 text-sm rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-purple-500/50 transition disabled:opacity-50"
        />
      </div>

      {/* Style */}
      <div className="mb-4">
        <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">Estilo</label>
        <StyleSelector selected={style} onSelect={setStyle} disabled={generating} />
      </div>

      {/* Duration */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">
          Duração: <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{duration}s</span>
        </label>
        <input
          type="range"
          min={20}
          max={60}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
          disabled={generating}
          className="w-full accent-purple-600"
        />
        <div className="flex justify-between text-[10px] text-[var(--text-tertiary)] mt-0.5">
          <span>20s</span>
          <span>60s</span>
        </div>
      </div>

      {/* Progress */}
      {activeJob && generating && (
        <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-purple-500/20 mb-4">
          <div className="flex justify-between mb-2">
            <span className="text-xs text-gray-300">
              {activeJob.current_step ? STEP_LABELS[activeJob.current_step] || activeJob.current_step : 'Iniciando...'}
            </span>
            <span className="text-xs text-purple-400 font-semibold">
              {Math.round(activeJob.progress * 100)}%
            </span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-surface-hover)' }}>
            <div
              className="h-full bg-purple-600 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.max(5, activeJob.progress * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {genError && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs mb-4">
          {genError}
        </div>
      )}

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={generating || !topic.trim()}
        className={`w-full py-3.5 rounded-xl border-none text-base font-semibold transition cursor-pointer ${
          generating || !topic.trim()
            ? 'bg-[var(--bg-surface-hover)] text-[var(--text-tertiary)] cursor-not-allowed'
            : 'bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:opacity-90'
        }`}
      >
        {generating ? 'Gerando...' : 'Gerar Vídeo'}
      </button>

      {/* Credits info */}
      {user && !generating && (
        <p className="text-center text-[11px] text-gray-600 mt-2">
          1 crédito será usado · {user.credits} disponíveis
        </p>
      )}

      {/* Credits modal placeholder */}
      {showCreditsModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-2xl p-8 max-w-sm w-full mx-4 text-center">
            <div className="text-4xl mb-4">💰</div>
            <h3 className="text-lg font-bold mb-2">Seus créditos acabaram</h3>
            <p className="text-sm text-gray-400 mb-1">Plano: <span className="text-gray-300 capitalize">{user?.plan || 'free'}</span></p>
            <p className="text-xs text-[var(--text-tertiary)] mb-6">Cada vídeo consome 1 crédito</p>
            <button
              disabled
              className="w-full py-3 rounded-xl bg-purple-600/30 text-purple-300 font-medium text-sm cursor-not-allowed opacity-50 mb-3"
            >
              Comprar créditos (em breve)
            </button>
            <button
              onClick={() => setShowCreditsModal(false)}
              className="text-sm text-gray-400 hover:text-white transition cursor-pointer"
            >
              Voltar
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
