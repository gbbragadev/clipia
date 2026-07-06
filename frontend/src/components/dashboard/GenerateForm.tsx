'use client'

import { strings } from '@/lib/strings';
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import {
  generateVideo,
  fetchJobStatus,
  fetchTemplates,
  STEP_LABELS,
  type GenerateParams,
  type JobStatusResponse,
  type VideoTemplateInfo,
} from '@/lib/editor-api'
import TemplateSelector from './TemplateSelector'
import StyleSelector, { type StyleValue } from './StyleSelector'
import WpmSlider from './WpmSlider'
import OpticalBalancePreview from './OpticalBalancePreview'
import ScriptDensityHeatmap from './ScriptDensityHeatmap'
import NarrationTimelineRuler from './NarrationTimelineRuler'
import KineticPreviewPanel from './KineticPreviewPanel'
import { useToast } from '@/components/ui/feedback'

interface GenerateFormProps {
  onJobComplete: () => void
  /** Chamado assim que o job é enfileirado — a grid mostra o card na hora e liga o polling. */
  onJobCreated?: () => void
  prefillTopic?: string
  prefillTrendContext?: string | null
  prefillTemplateId?: string
  prefillStyle?: StyleValue
}

export default function GenerateForm({ onJobComplete, onJobCreated, prefillTopic, prefillTrendContext, prefillTemplateId, prefillStyle }: GenerateFormProps) {
  const { user, refreshUser } = useAuth()
  const { success, error: toastError, info } = useToast()

  const [topic, setTopic] = useState('')
  const [trendContext, setTrendContext] = useState<string | null>(null)
  const [style, setStyle] = useState<StyleValue>('educational')
  const [templateId, setTemplateId] = useState('stock_narration')
  const [duration, setDuration] = useState(45)
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<JobStatusResponse | null>(null)
  const [showCreditsModal, setShowCreditsModal] = useState(false)
  const [script, setScript] = useState('')
  const [wpm, setWpm] = useState(150)
  const [showAdvancedScript, setShowAdvancedScript] = useState(false)
  const [voiceProvider, setVoiceProvider] = useState<'edge' | 'elevenlabs'>('edge')
  const [sfxEnabled, setSfxEnabled] = useState(true)
  const [musicEnabled, setMusicEnabled] = useState(true)
  const [templates, setTemplates] = useState<VideoTemplateInfo[]>([])

  const selectedTemplate = templates.find((template) => template.id === templateId)
  const isFallbackAiTemplate = templateId === 'novelinha_historica'
  const supportsDefaultPremiumVoice = Boolean(
    (selectedTemplate?.default_voice_provider === 'elevenlabs' && selectedTemplate.default_voice_id)
      || isFallbackAiTemplate,
  )
  const creditCost = selectedTemplate?.credit_costs?.[voiceProvider]
    ?? (isFallbackAiTemplate ? 5 : voiceProvider === 'elevenlabs' ? 2 : 1)
  const edgeCreditCost = selectedTemplate?.credit_costs?.edge ?? (isFallbackAiTemplate ? 5 : 1)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastRequestRef = useRef<GenerateParams | null>(null)
  const appliedPrefillRef = useRef<string | null>(null)

  // Poll active job
  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    let failures = 0
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchJobStatus(jobId)
        failures = 0
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
      } catch (err) {
        // Tolera blips transitorios (rede/502 momentaneo); so desiste apos ~10s de falhas seguidas,
        // em vez de engolir o erro e deixar o spinner girando pra sempre (bug do 502 do amigo).
        failures += 1
        if (failures >= 5) {
          if (pollRef.current) clearInterval(pollRef.current)
          setGenerating(false)
          setGenError(
            err instanceof Error
              ? err.message
              : 'Perdemos a conexão com o servidor. Recarregue a página para ver o status do seu vídeo.',
          )
        }
      }
    }, 2000)
  }, [onJobComplete, refreshUser])

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    fetchTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]))
  }, [])

  // Pre-preenche o tema (e o contexto da tendencia) quando o usuario clica num trend do painel "Em alta"
  useEffect(() => {
    if (prefillTopic) {
      setTopic(prefillTopic)
      setTrendContext(prefillTrendContext ?? null)
    }
    if (prefillStyle) {
      setStyle(prefillStyle)
    }
  }, [prefillTopic, prefillTrendContext, prefillStyle])

  // Aplica template prefill apenas quando templates carregam — guarda com ref composto (topic|templateId) para re-aplicar em nova seleção de painel
  useEffect(() => {
    if (!prefillTemplateId || templates.length === 0) return
    const prefillKey = `${prefillTopic}|${prefillTemplateId}`
    if (appliedPrefillRef.current === prefillKey) return // já foi aplicado nesta seleção
    handleTemplateSelect(prefillTemplateId)
    appliedPrefillRef.current = prefillKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillTemplateId, templates, prefillTopic])

  const handleTemplateSelect = (id: string) => {
    const nextTemplate = templates.find((template) => template.id === id)
    setTemplateId(id)
    if ((nextTemplate?.default_voice_provider === 'elevenlabs' && nextTemplate.default_voice_id) || id === 'novelinha_historica') {
      setVoiceProvider('elevenlabs')
    } else if (voiceProvider === 'elevenlabs') {
      setVoiceProvider('edge')
    }
  }

  const handleGenerate = async () => {
    if (!topic.trim() || generating) return

    if (user && user.credits < creditCost) {
      setShowCreditsModal(true)
      info('Sem créditos suficientes', 'Adicione créditos para iniciar uma nova geração.')
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
        voice_provider: voiceProvider,
        voice_config: voiceProvider === 'elevenlabs' && selectedTemplate?.default_voice_id
          ? { voice_id: selectedTemplate.default_voice_id }
          : undefined,
        sfx_enabled: sfxEnabled,
        music_enabled: musicEnabled,
        trend_context: trendContext ?? undefined,
      }
      lastRequestRef.current = params
      const result = await generateVideo(params)
      startPolling(result.job_id)
      onJobCreated?.()
      success('Video enfileirado', 'A geracao foi iniciada com sucesso.')
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
      const message = err instanceof Error ? err.message : 'Erro ao iniciar geração'
      setGenError(message)
      toastError('Não foi possível iniciar a geração', message)
    }
  }

  return (
    <section>
      <h2 className="text-xl font-bold mb-6">Criar novo vídeo</h2>

      {/* Topic */}
      <div className="mb-4">
        <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">Tema do vídeo — escreva o que quiser</label>
        <input
          type="text"
          value={topic}
          onChange={(e) => { setTopic(e.target.value); setTrendContext(null) }}
          onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate() }}
          placeholder="Ex: 5 curiosidades sobre o oceano profundo"
          disabled={generating}
          className="w-full px-4 py-3 text-sm rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-coral/50 transition disabled:opacity-50"
        />
      </div>

      <OpticalBalancePreview text={topic} />

      {/* Template */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-2">Template</label>
        <TemplateSelector
          selected={templateId}
          onSelect={handleTemplateSelect}
          disabled={generating}
          templates={templates}
          voiceProvider={voiceProvider}
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
          min={15}
          max={180}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
          disabled={generating}
          className="w-full accent-coral"
        />
        <div className="flex justify-between text-[10px] text-[var(--text-tertiary)] mt-0.5">
          <span>15s</span>
          <span>180s</span>
        </div>
      </div>

      {/* Voice Provider */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">Voz</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setVoiceProvider('edge')}
            disabled={generating}
            className={`flex-1 py-2.5 px-3 rounded-xl border text-xs font-medium transition ${
              voiceProvider === 'edge'
                ? 'border-coral/50 bg-coral/10 text-coral'
                : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-coral/30'
            } disabled:opacity-50 cursor-pointer`}
          >
            <div className="font-semibold">Edge TTS</div>
            <div className="text-[10px] opacity-60 mt-0.5">
              Edge · {edgeCreditCost} credito{edgeCreditCost > 1 ? 's' : ''}
            </div>
          </button>
          <button
            type="button"
            onClick={() => {
              if (supportsDefaultPremiumVoice) setVoiceProvider('elevenlabs')
            }}
            disabled={generating || !supportsDefaultPremiumVoice}
            className={`flex-1 py-2.5 px-3 rounded-xl border text-xs font-medium transition ${
              voiceProvider === 'elevenlabs'
                ? 'border-azure/50 bg-azure/10 text-azure'
                : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-azure/30'
            } disabled:opacity-50 cursor-pointer`}
          >
            <div className="font-semibold">ElevenLabs</div>
            <div className="text-[10px] opacity-60 mt-0.5">
              {supportsDefaultPremiumVoice ? `Premium · ${creditCost} creditos` : 'Premium no template IA'}
            </div>
          </button>
        </div>
      </div>

      {/* Audio */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-2">Áudio</label>
        <div className="flex flex-col gap-2">
          {([
            { on: sfxEnabled, set: setSfxEnabled, label: 'Efeitos sonoros', hint: 'Whoosh nas transições de cena' },
            { on: musicEnabled, set: setMusicEnabled, label: 'Música de fundo', hint: 'Trilha automática pelo tema do template' },
          ] as const).map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => item.set(!item.on)}
              disabled={generating}
              className={`flex items-center justify-between py-2.5 px-3 rounded-xl border text-xs font-medium transition cursor-pointer disabled:opacity-50 ${
                item.on
                  ? 'border-coral/50 bg-coral/10 text-coral'
                  : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-coral/30'
              }`}
            >
              <span className="flex flex-col items-start text-left">
                <span className="font-semibold">{item.label}</span>
                <span className="text-[10px] opacity-60">{item.hint}</span>
              </span>
              <span
                className={`relative w-9 h-5 rounded-full transition shrink-0 ${item.on ? 'bg-coral' : 'bg-[var(--bg-surface-hover)]'}`}
              >
                <span
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                  style={{ left: item.on ? '18px' : '2px' }}
                />
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Advanced Script Section */}
      <div className="mb-5">
        <button
          type="button"
          onClick={() => setShowAdvancedScript(!showAdvancedScript)}
          disabled={generating}
          className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition cursor-pointer disabled:opacity-50"
        >
          <span className="transition-transform" style={{ transform: showAdvancedScript ? 'rotate(90deg)' : 'rotate(0deg)' }}>
            ▶
          </span>
          Roteiro avançado (opcional)
        </button>

        {showAdvancedScript && (
          <div className="mt-3 space-y-4">
            <p className="text-[11px] leading-relaxed text-[var(--text-tertiary)]">
              Deixe em branco para a IA criar o roteiro a partir do tema acima. Preencha
              apenas se quiser escrever o seu próprio — cada parágrafo vira uma cena.
            </p>
            <div>
              <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">
                Seu roteiro (uma cena por parágrafo, separadas por linha em branco)
              </label>
              <textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                disabled={generating}
                rows={6}
                placeholder={"Exemplo (apague e escreva o seu):\nPrimeira cena da narração aqui.\n\nSegunda cena, depois de uma linha em branco.\nCada parágrafo vira uma cena do vídeo."}
                className="w-full px-4 py-3 text-sm rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-coral/50 transition disabled:opacity-50 resize-y font-mono"
              />
            </div>

            <WpmSlider value={wpm} onChange={setWpm} disabled={generating} />

            {script.trim() && (
              <ScriptDensityHeatmap script={script} duration={duration} wpm={wpm} />
            )}

            {script.trim() && (
              <NarrationTimelineRuler script={script} duration={duration} wpm={wpm} />
            )}

            {script.trim() && (
              <KineticPreviewPanel script={script} />
            )}
          </div>
        )}
      </div>

      {/* Progress */}
      {activeJob && generating && (
        <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-coral/20 mb-4">
          <div className="flex justify-between mb-2">
            <span className="text-xs text-gray-300">
              {activeJob.current_step ? STEP_LABELS[activeJob.current_step] || activeJob.current_step : 'Iniciando...'}
            </span>
            <span className="text-xs text-coral font-semibold">
              {Math.round(activeJob.progress * 100)}%
            </span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-surface-hover)' }}>
            <div
              className="h-full bg-coral rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.max(5, activeJob.progress * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {genError && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs mb-4 flex items-center justify-between gap-3">
          <span>{genError}</span>
          <button
            type="button"
            onClick={() => {
              if (lastRequestRef.current) {
                setTopic(lastRequestRef.current.topic)
                setStyle(lastRequestRef.current.style as StyleValue)
                setDuration(lastRequestRef.current.duration_target)
                setTemplateId(lastRequestRef.current.template_id)
              }
              handleGenerate()
            }}
            className="shrink-0 rounded-lg bg-coral px-3 py-1.5 text-[11px] font-semibold text-white"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={generating || topic.trim().length < 10}
        className={`w-full py-3.5 rounded-xl border-none text-base font-semibold transition cursor-pointer ${
          generating || topic.trim().length < 10
            ? 'bg-[var(--bg-surface-hover)] text-[var(--text-tertiary)] cursor-not-allowed'
            : 'bg-gradient-to-r from-coral to-azure text-white hover:opacity-90'
        }`}
      >
        {generating ? strings.dashboard.generate.loading : 'Gerar Vídeo'}
      </button>

      {/* Credits info */}
      {user && !generating && (
        <p className="text-center text-[11px] text-gray-600 mt-2">
          {creditCost} crédito{creditCost > 1 ? 's' : ''} será{creditCost > 1 ? 'ão' : ''} usado{creditCost > 1 ? 's' : ''} · {user.credits} disponíve{user.credits === 1 ? 'l' : 'is'}
        </p>
      )}

      {/* Credits modal placeholder */}
      {showCreditsModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-2xl p-8 max-w-sm w-full mx-4 text-center">
            <div className="text-4xl mb-4">💰</div>
            <h3 className="text-lg font-bold mb-2">Seus créditos acabaram</h3>
            <p className="text-sm text-gray-400 mb-1">Plano: <span className="text-gray-300 capitalize">{user?.plan || 'free'}</span></p>
            <p className="text-xs text-[var(--text-tertiary)] mb-6">Este template consome {creditCost} crédito{creditCost > 1 ? 's' : ''}</p>
            <a
              href="/dashboard/credits"
              className="block w-full py-3 rounded-xl bg-coral text-white font-medium text-sm hover:bg-coral transition mb-3"
            >
              Comprar créditos
            </a>
            <button
              onClick={() => setShowCreditsModal(false)}
              className="text-sm text-gray-400 hover:text-white transition cursor-pointer"
            >
              {strings.common.back}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
