'use client'

import { strings } from '@/lib/strings';
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import {
  generateVideo,
  fetchTemplates,
  fetchVoices,
  type GenerateParams,
  type VideoTemplateInfo,
  type VoiceInfo,
} from '@/lib/editor-api'
import TemplateSelector from './TemplateSelector'
import StyleSelector, { type StyleValue } from './StyleSelector'
import WpmSlider from './WpmSlider'
import OpticalBalancePreview from './OpticalBalancePreview'
import ScriptDensityHeatmap from './ScriptDensityHeatmap'
import NarrationTimelineRuler from './NarrationTimelineRuler'
import KineticPreviewPanel from './KineticPreviewPanel'
import { useToast } from '@/components/ui/feedback'
import { Modal } from '@/components/ui/Modal'

interface GenerateFormProps {
  /** Chamado assim que o job é enfileirado — a grid mostra o card na hora e liga o polling. */
  onJobCreated?: () => void
  prefillTopic?: string
  prefillTrendContext?: string | null
  prefillTemplateId?: string
  prefillStyle?: StyleValue
}

export default function GenerateForm({ onJobCreated, prefillTopic, prefillTrendContext, prefillTemplateId, prefillStyle }: GenerateFormProps) {
  const { user } = useAuth()
  const { success, error: toastError, info } = useToast()

  const [topic, setTopic] = useState('')
  const [trendContext, setTrendContext] = useState<string | null>(null)
  const [style, setStyle] = useState<StyleValue>('educational')
  const [templateId, setTemplateId] = useState('stock_narration')
  const [duration, setDuration] = useState(45)
  // `generating` cobre APENAS o POST /generate (~1s): depois do 202 o formulário
  // libera e a grid (polling próprio do dashboard) assume o acompanhamento.
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [showCreditsModal, setShowCreditsModal] = useState(false)
  const [script, setScript] = useState('')
  const [wpm, setWpm] = useState(150)
  const [showAdvancedScript, setShowAdvancedScript] = useState(false)
  const [voiceProvider, setVoiceProvider] = useState<'edge' | 'elevenlabs'>('edge')
  // Narração: single (1 voz, escolhível) ou dialogue (2 vozes — só em templates capable)
  const [narrationMode, setNarrationMode] = useState<'single' | 'dialogue'>('single')
  const [voiceId, setVoiceId] = useState<string | null>(null) // null = default do template
  const [voices, setVoices] = useState<VoiceInfo[]>([])
  const [sfxEnabled, setSfxEnabled] = useState(true)
  const [musicEnabled, setMusicEnabled] = useState(true)
  const [templates, setTemplates] = useState<VideoTemplateInfo[]>([])
  // Lote: variações do MESMO tema (comparar versões) OU fila de vários temas.
  const [variations, setVariations] = useState(1)
  const [batchMode, setBatchMode] = useState(false)
  const [batchTopics, setBatchTopics] = useState('')
  // Temas aguardando confirmação de custo no Modal (guardrail: custo ANTES de ação paga).
  const [confirmTopics, setConfirmTopics] = useState<string[] | null>(null)

  const selectedTemplate = templates.find((template) => template.id === templateId)
  const isFallbackAiTemplate = templateId === 'novelinha_historica'
  const supportsDefaultPremiumVoice = Boolean(
    (selectedTemplate?.default_voice_provider === 'elevenlabs' && selectedTemplate.default_voice_id)
      || isFallbackAiTemplate,
  )
  const dialogueCapable = Boolean(selectedTemplate?.dialogue_capable)
  // Diálogo sintetiza com 2 vozes ElevenLabs → custa o pricing elevenlabs do template
  const effectiveProvider = narrationMode === 'dialogue' ? 'elevenlabs' : voiceProvider
  const creditCost = selectedTemplate?.credit_costs?.[effectiveProvider]
    ?? (isFallbackAiTemplate ? 5 : effectiveProvider === 'elevenlabs' ? 2 : 1)
  const edgeCreditCost = selectedTemplate?.credit_costs?.edge ?? (isFallbackAiTemplate ? 5 : 1)
  const elevenCreditCost = selectedTemplate?.credit_costs?.elevenlabs ?? (isFallbackAiTemplate ? 5 : 2)
  // Vozes selecionáveis do provider ativo (modo single)
  const providerVoices = voices.filter((v) => v.provider === voiceProvider)

  const MAX_BATCH = 5 // fila solo: 1 vídeo por vez — cap evita fila de horas
  const batchList = batchTopics
    .split('\n')
    .map((t) => t.trim())
    .filter((t) => t.length >= 10)
    .slice(0, MAX_BATCH)
  const runCount = batchMode ? batchList.length : variations
  const totalCost = runCount * creditCost
  const canSubmit = batchMode ? batchList.length > 0 : topic.trim().length >= 10

  const lastRequestRef = useRef<GenerateParams | null>(null)
  const appliedPrefillRef = useRef<string | null>(null)

  useEffect(() => {
    fetchTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]))
    fetchVoices()
      .then(setVoices)
      .catch(() => setVoices([]))
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
    setVoiceId(null) // volta ao default do template novo
    if (!nextTemplate?.dialogue_capable) setNarrationMode('single')
    if ((nextTemplate?.default_voice_provider === 'elevenlabs' && nextTemplate.default_voice_id) || id === 'novelinha_historica') {
      setVoiceProvider('elevenlabs')
    } else if (voiceProvider === 'elevenlabs') {
      setVoiceProvider('edge')
    }
  }

  const buildParams = (t: string, withTrend: boolean): GenerateParams => {
    // Voz escolhida no select > default do template (elevenlabs precisa de voice_id explícito)
    const chosenVoiceId = narrationMode === 'dialogue'
      ? undefined // as 2 vozes do diálogo são fixas no backend
      : voiceId
        ?? (voiceProvider === 'elevenlabs' ? selectedTemplate?.default_voice_id : undefined)
    return {
      topic: t,
      style,
      duration_target: duration,
      template_id: templateId,
      voice_provider: voiceProvider,
      voice_config: chosenVoiceId ? { voice_id: chosenVoiceId } : undefined,
      sfx_enabled: sfxEnabled,
      music_enabled: musicEnabled,
      trend_context: withTrend ? trendContext ?? undefined : undefined,
      narration_mode: narrationMode,
    }
  }

  /** Enfileira 1..N gerações em sequência (débito atômico e estorno são POR job no backend). */
  const startGeneration = async (topics: string[]) => {
    setConfirmTopics(null)
    setGenerating(true)
    setGenError(null)
    let queued = 0
    try {
      for (const t of topics) {
        // trendContext pertence ao tema digitado: vale nas variações, não no lote multi-tema
        const params = buildParams(t, !batchMode)
        lastRequestRef.current = params
        await generateVideo(params)
        queued += 1
        // 202 aceito: a grid mostra o card na hora e o polling dela assume o tracking
        onJobCreated?.()
      }
      success(
        queued === 1 ? 'Vídeo na fila' : `${queued} vídeos na fila`,
        'Acompanhe o progresso nos cards em "Seus vídeos". Pode gerar outros enquanto isso.',
      )
      if (batchMode) {
        setBatchTopics('')
      } else {
        setTopic('')
        setTrendContext(null)
      }
      setVariations(1)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao iniciar geração'
      // Honestidade em falha parcial: diz quantos ENTRARAM antes do erro.
      setGenError(queued > 0 ? `${queued} de ${topics.length} vídeos entraram na fila. Depois disso: ${message}` : message)
      toastError('Não foi possível enfileirar tudo', message)
    } finally {
      setGenerating(false)
    }
  }

  const handleGenerate = () => {
    if (generating || !canSubmit) return
    const topics = batchMode ? batchList : Array<string>(variations).fill(topic.trim())

    if (user && user.credits < topics.length * creditCost) {
      setShowCreditsModal(true)
      info('Sem créditos suficientes', 'Adicione créditos para iniciar as gerações.')
      return
    }
    // Mais de um vídeo = custo multiplicado: SEMPRE confirmar no Modal antes.
    if (topics.length > 1) {
      setConfirmTopics(topics)
      return
    }
    startGeneration(topics)
  }

  return (
    <section>
      <div className="mb-6 flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-coral/15 text-coral" aria-hidden>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.7 4.6L18 9.3l-4.3 1.7L12 15l-1.7-4L6 9.3l4.3-1.7z"/><path d="M19 13l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7z"/></svg>
        </span>
        <div>
          <h2 className="font-display text-2xl font-extrabold leading-tight">Criar novo vídeo</h2>
          <p className="text-xs text-[var(--text-tertiary)]">Digite o tema. O resto é com a gente.</p>
        </div>
      </div>

      {/* Topic — o campo-herói do produto (single) OU fila de temas (lote) */}
      <div className="mb-4">
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <label className="block text-xs text-[var(--text-tertiary)]">
            {batchMode ? `Vários temas — um por linha (até ${MAX_BATCH})` : 'Tema do vídeo — escreva o que quiser'}
          </label>
          <button
            type="button"
            onClick={() => { setBatchMode(!batchMode); setGenError(null) }}
            disabled={generating}
            className="shrink-0 text-[11px] text-azure hover:text-azure/80 transition cursor-pointer disabled:opacity-50"
          >
            {batchMode ? '← Voltar para um tema' : 'Gerar vários de uma vez'}
          </button>
        </div>
        {batchMode ? (
          <>
            <textarea
              value={batchTopics}
              onChange={(e) => setBatchTopics(e.target.value)}
              rows={5}
              placeholder={'Ex:\n5 curiosidades sobre o oceano profundo\nA história do café no Brasil\nPor que os gatos ronronam'}
              disabled={generating}
              className="w-full px-5 py-4 text-base rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-coral/60 focus:ring-2 focus:ring-coral/20 transition disabled:opacity-50 resize-y"
            />
            <p className="mt-1.5 text-[11px] text-[var(--text-tertiary)]">
              {batchList.length === 0
                ? 'Cada linha com pelo menos 10 caracteres vira um vídeo.'
                : `${batchList.length} tema${batchList.length > 1 ? 's' : ''} pronto${batchList.length > 1 ? 's' : ''} para gerar — cada um vira um vídeo na fila.`}
            </p>
          </>
        ) : (
          <>
            <input
              type="text"
              value={topic}
              onChange={(e) => { setTopic(e.target.value); setTrendContext(null) }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate() }}
              placeholder="Ex: 5 curiosidades sobre o oceano profundo"
              disabled={generating}
              className="w-full px-5 py-4 text-base rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-coral/60 focus:ring-2 focus:ring-coral/20 transition disabled:opacity-50"
            />
            {/* Transparência do prefill: o contexto da tendência viaja junto com o tema */}
            {trendContext && (
              <span className="mt-1.5 inline-flex items-center gap-1.5 rounded-full border border-coral/25 bg-coral/10 px-2.5 py-1 text-[11px] text-coral">
                🔥 Baseado numa tendência do painel &quot;Em alta&quot; — o roteiro usa esse contexto
              </span>
            )}
          </>
        )}
      </div>

      {!batchMode && <OpticalBalancePreview text={topic} />}

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

      {/* Narração: provider + voz escolhível + modo diálogo (quando o template aceita) */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-1.5">Narração</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => { setVoiceProvider('edge'); setNarrationMode('single'); setVoiceId(null) }}
            disabled={generating}
            className={`flex-1 py-2.5 px-3 rounded-xl border text-xs font-medium transition ${
              narrationMode === 'single' && voiceProvider === 'edge'
                ? 'border-coral/50 bg-coral/10 text-coral'
                : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-coral/30'
            } disabled:opacity-50 cursor-pointer`}
          >
            <div className="font-semibold">Edge TTS</div>
            <div className="text-[10px] opacity-60 mt-0.5">
              Edge · {edgeCreditCost} crédito{edgeCreditCost > 1 ? 's' : ''}
            </div>
          </button>
          <button
            type="button"
            onClick={() => {
              if (supportsDefaultPremiumVoice) { setVoiceProvider('elevenlabs'); setNarrationMode('single'); setVoiceId(null) }
            }}
            disabled={generating || !supportsDefaultPremiumVoice}
            className={`flex-1 py-2.5 px-3 rounded-xl border text-xs font-medium transition ${
              narrationMode === 'single' && voiceProvider === 'elevenlabs'
                ? 'border-azure/50 bg-azure/10 text-azure'
                : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-azure/30'
            } disabled:opacity-50 cursor-pointer`}
          >
            <div className="font-semibold">ElevenLabs</div>
            <div className="text-[10px] opacity-60 mt-0.5">
              {supportsDefaultPremiumVoice ? `Premium · ${elevenCreditCost} créditos` : 'Premium no template IA'}
            </div>
          </button>
          {dialogueCapable && (
            <button
              type="button"
              onClick={() => setNarrationMode('dialogue')}
              disabled={generating}
              className={`flex-1 py-2.5 px-3 rounded-xl border text-xs font-medium transition ${
                narrationMode === 'dialogue'
                  ? 'border-mint/50 bg-mint/10 text-mint'
                  : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-mint/30'
              } disabled:opacity-50 cursor-pointer`}
            >
              <div className="font-semibold">Diálogo (2 vozes)</div>
              <div className="text-[10px] opacity-60 mt-0.5">
                Conversa · {elevenCreditCost} créditos
              </div>
            </button>
          )}
        </div>

        {/* Voz específica do provider (modo single) — o override já era suportado no backend */}
        {narrationMode === 'single' && providerVoices.length > 1 && (
          <select
            value={voiceId ?? ''}
            onChange={(e) => setVoiceId(e.target.value || null)}
            disabled={generating}
            aria-label="Escolher a voz da narração"
            className="mt-2 w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-coral/50 transition disabled:opacity-50 cursor-pointer"
          >
            <option value="">Voz padrão do template</option>
            {providerVoices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}{v.gender ? ` · ${v.gender === 'female' ? 'feminina' : 'masculina'}` : ''}
              </option>
            ))}
          </select>
        )}
        {narrationMode === 'dialogue' && (
          <p className="mt-2 text-[11px] text-[var(--text-tertiary)]">
            O roteiro vira uma conversa entre duas vozes premium (Fernanda e um segundo narrador) — ótimo para dramas e debates.
          </p>
        )}
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

      {/* Variações — mesmo tema, N versões para comparar (só no modo single) */}
      {!batchMode && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] px-3.5 py-2.5">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-[var(--text-primary)]">Variações</div>
            <div className="text-[10px] text-[var(--text-tertiary)]">Mesmo tema, roteiros diferentes — compare e fique com o melhor</div>
          </div>
          <div className="flex gap-1" role="radiogroup" aria-label="Quantidade de variações">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={variations === n}
                onClick={() => setVariations(n)}
                disabled={generating}
                className={`h-8 w-8 rounded-lg border text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${
                  variations === n
                    ? 'border-coral/50 bg-coral/15 text-coral'
                    : 'border-[var(--border-default)] bg-transparent text-[var(--text-tertiary)] hover:border-coral/30'
                }`}
              >
                {n}×
              </button>
            ))}
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
        disabled={generating || !canSubmit}
        className={`w-full py-3.5 rounded-xl border-none text-base font-semibold transition cursor-pointer ${
          generating || !canSubmit
            ? 'bg-[var(--bg-surface-hover)] text-[var(--text-tertiary)] cursor-not-allowed'
            : 'bg-gradient-to-r from-coral to-azure text-white hover:opacity-90'
        }`}
      >
        {generating
          ? strings.dashboard.generate.loading
          : runCount > 1
            ? `Gerar ${runCount} vídeos`
            : 'Gerar Vídeo'}
      </button>

      {/* Botão desabilitado sempre explica o porquê (DESIGN.md) */}
      {!generating && !canSubmit && (
        <p className="text-center text-[11px] text-[var(--text-tertiary)] mt-2">
          {batchMode
            ? 'Escreva pelo menos um tema com 10+ caracteres (um por linha) para liberar a geração.'
            : 'Escreva o tema com pelo menos 10 caracteres para liberar a geração.'}
        </p>
      )}

      {/* Credits info — custo antes da ação */}
      {user && !generating && canSubmit && (
        <p className="text-center text-[11px] text-[var(--text-tertiary)] mt-2">
          {runCount > 1
            ? `${totalCost} créditos (${runCount} × ${creditCost}) serão usados · ${user.credits} disponíveis`
            : `${creditCost} crédito${creditCost > 1 ? 's' : ''} será${creditCost > 1 ? 'ão' : ''} usado${creditCost > 1 ? 's' : ''} · ${user.credits} disponíve${user.credits === 1 ? 'l' : 'is'}`}
        </p>
      )}

      {/* Confirmação de lote — custo N× SEMPRE antes de debitar (DESIGN.md) */}
      <Modal open={confirmTopics !== null} onClose={() => setConfirmTopics(null)} labelledBy="lote-modal-titulo">
        <h3 id="lote-modal-titulo" className="text-lg font-bold mb-2">
          Gerar {confirmTopics?.length} vídeos?
        </h3>
        {confirmTopics && !batchMode ? (
          <p className="text-sm text-[var(--text-secondary)] mb-3">
            {confirmTopics.length} variações do tema <span className="text-[var(--text-primary)]">&quot;{confirmTopics[0]}&quot;</span> — roteiros diferentes para você comparar.
          </p>
        ) : (
          <ul className="mb-3 max-h-40 space-y-1 overflow-y-auto text-sm text-[var(--text-secondary)]">
            {confirmTopics?.map((t, i) => (
              <li key={i} className="truncate rounded-lg bg-[var(--bg-surface)] px-3 py-1.5">{t}</li>
            ))}
          </ul>
        )}
        <p className="mb-5 rounded-xl border border-coral/25 bg-coral/10 px-3.5 py-2.5 text-sm text-coral">
          Custo total: <strong>{(confirmTopics?.length ?? 0) * creditCost} créditos</strong> ({confirmTopics?.length} × {creditCost})
          {user ? <span className="text-coral/80"> · você tem {user.credits}</span> : null}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => confirmTopics && startGeneration(confirmTopics)}
            className="flex-1 py-3 rounded-xl bg-coral text-white font-semibold text-sm hover:opacity-90 transition cursor-pointer"
          >
            Confirmar e gerar
          </button>
          <button
            type="button"
            onClick={() => setConfirmTopics(null)}
            className="flex-1 py-3 rounded-xl bg-white/5 border border-white/10 text-[var(--text-secondary)] font-medium text-sm hover:bg-white/10 transition cursor-pointer"
          >
            Cancelar
          </button>
        </div>
      </Modal>

      {/* Créditos insuficientes — modal acessível (portal + Esc + foco) */}
      <Modal open={showCreditsModal} onClose={() => setShowCreditsModal(false)} labelledBy="creditos-modal-titulo" className="text-center">
        <div className="text-4xl mb-4" aria-hidden>💰</div>
        <h3 id="creditos-modal-titulo" className="text-lg font-bold mb-2">Seus créditos acabaram</h3>
        <p className="text-sm text-[var(--text-secondary)] mb-1">
          Plano: <span className="text-[var(--text-primary)] capitalize">{user?.plan || 'free'}</span>
        </p>
        <p className="text-xs text-[var(--text-tertiary)] mb-6">Este template consome {creditCost} crédito{creditCost > 1 ? 's' : ''}</p>
        <a
          href="/dashboard/credits"
          className="block w-full py-3 rounded-xl bg-coral text-white font-medium text-sm hover:opacity-90 transition mb-3"
        >
          Comprar créditos
        </a>
        <button
          onClick={() => setShowCreditsModal(false)}
          className="text-sm text-[var(--text-secondary)] hover:text-white transition cursor-pointer"
        >
          {strings.common.back}
        </button>
      </Modal>
    </section>
  )
}
