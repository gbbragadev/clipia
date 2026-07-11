'use client'

import { useRef, useState, useEffect } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'
import { useToast } from '@/components/ui/feedback'
import { Modal } from '@/components/ui/Modal'
import { useAuth } from '@/contexts/AuthContext'
import { CostChip } from './CostChip'

const QUICK_PROMPTS = [
  { label: 'Melhorar gancho', prompt: 'Reescreva a cena 1 com um gancho mais forte e provocativo que prenda nos primeiros 3 segundos' },
  { label: 'Mais engajante', prompt: 'Torne o roteiro mais engajante e conversacional, como se estivesse falando com um amigo' },
  { label: 'Adicionar humor', prompt: 'Adicione toques de humor natural sem perder o conteudo informativo' },
  { label: 'CTA melhor', prompt: 'Melhore a ultima cena com um call-to-action mais efetivo que incentive o follow' },
]

interface Suggestion {
  type: string
  scene_index: number
  new_text: string
  reason: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  suggestions?: Suggestion[]
}

export function AIAssistant() {
  const { jobId, composition, updateScene, updateAudio, selectScene, setActivePanel } = useEditor()
  const { error: toastError, info } = useToast()
  const { user, refreshUser } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [appliedSuggestions, setAppliedSuggestions] = useState<Set<string>>(new Set())
  const [applyingKey, setApplyingKey] = useState<string | null>(null)
  // Voz premium: regravar a narração no apply custa 2 créditos → confirmação antes (DESIGN.md)
  const [pendingApply, setPendingApply] = useState<{ msgIndex: number; sugIndex: number; suggestion: Suggestion } | null>(null)
  // Custo diferido do ai-suggest: cada consulta soma 0,5 crédito ao pending_credits
  // do job (cobrado no próximo export). A API devolve o acumulado — exibimos ao vivo.
  const [pendingCredits, setPendingCredits] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!composition || !text.trim() || loading) return
    const trimmed = text.trim()
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: trimmed }])

    try {
      const token = getToken()
      const res = await fetch(`/api/v1/jobs/${jobId}/ai-suggest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: trimmed,
          context: {
            title: composition.title,
            scenes: composition.scenes,
          },
        }),
      })
      if (!res.ok) throw new Error(await readApiError(res, 'Erro ao consultar IA'))
      const data = await res.json()
      if (typeof data.pending_credits === 'number') setPendingCredits(data.pending_credits)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.general_feedback || '',
        suggestions: data.suggestions || [],
      }])
    } catch {
      toastError('Não foi possível consultar a IA', 'Tente novamente em alguns segundos.')
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Erro ao consultar IA. Tente novamente.',
      }])
    } finally {
      setLoading(false)
    }
  }

  const isPremiumVoice = composition?.voiceConfig?.voiceProvider === 'elevenlabs'

  // Gate de custo: voz premium regrava a narração inteira (2 créditos) → Modal decide.
  const requestApply = (msgIndex: number, sugIndex: number, suggestion: Suggestion) => {
    if (isPremiumVoice) {
      setPendingApply({ msgIndex, sugIndex, suggestion })
    } else {
      void handleApply(msgIndex, sugIndex, suggestion, true)
    }
  }

  const handleApply = async (msgIndex: number, sugIndex: number, suggestion: Suggestion, regenerate: boolean) => {
    if (!composition) return
    setPendingApply(null)
    const key = `${msgIndex}-${sugIndex}`

    // 1. Update scene text in composition state
    updateScene(suggestion.scene_index, { text: suggestion.new_text })

    if (!regenerate) {
      // Só o texto: o aviso de narração desatualizada (narrationStale) guia o regen depois.
      setAppliedSuggestions(prev => new Set(prev).add(key))
      info('Texto aplicado', 'A narração não foi regravada — regenere na aba Voz quando terminar de editar.')
      selectScene(suggestion.scene_index)
      setActivePanel('scenes')
      return
    }

    setApplyingKey(key)

    // 2. Build the full text with the new scene applied
    const updatedScenes = composition.scenes.map((s, i) =>
      i === suggestion.scene_index ? { ...s, text: suggestion.new_text } : s
    )
    const fullText = updatedScenes.map(s => s.text).join(' ')

    // 3. Regenerate TTS + Whisper transcription with updated text
    try {
      const token = getToken()
      const res = await fetch(`/api/v1/jobs/${jobId}/regenerate-tts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          text: fullText,
          voice_id: composition.voiceConfig?.voiceId || 'pt-BR-AntonioNeural',
          // Sem isso o backend caía no caminho Edge com voice_id premium → 422 e o
          // apply "funcionava" só no texto. Provider explícito = custo e voz corretos.
          voice_provider: composition.voiceConfig?.voiceProvider || 'edge',
          rate: composition.voiceConfig?.rate ?? -10,
          pitch: composition.voiceConfig?.pitch ?? 5,
        }),
      })
      if (!res.ok) throw new Error(await readApiError(res, 'Falha ao regerar narração'))
      const data = await res.json()
      const audioUrl = `${data.audio_url}?t=${Date.now()}`
      updateAudio(data.words, audioUrl)
      setAppliedSuggestions(prev => new Set(prev).add(key))
      if (data.words_stale) {
        info(
          'Narração gerada, mas as legendas podem ter ficado dessincronizadas',
          'A transcrição do áudio novo falhou; mantivemos os tempos antigos. Regenere na aba Voz para tentar sincronizar.',
        )
      }
      if (isPremiumVoice) await refreshUser()
    } catch (err) {
      console.error('AI apply regeneration failed:', err)
      // Text is already updated, just mark as applied with warning
      setAppliedSuggestions(prev => new Set(prev).add(key))
      info('Rerender parcial falhou', 'O texto foi salvo, mas a narração não foi atualizada.')
    } finally {
      setApplyingKey(null)
    }

    selectScene(suggestion.scene_index)
    setActivePanel('scenes')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      gap: 12,
    }}>
      {/* Custo ANTES da ação (DESIGN.md): consulta soma 0,5 crédito ao próximo export */}
      <div style={{ padding: '0 2px' }}>
        <CostChip>
          0,5 crédito por consulta, somado ao próximo export
          {pendingCredits != null ? ` · acumulado: ${pendingCredits.toLocaleString('pt-BR')}` : ''}
        </CostChip>
      </div>

      {/* Quick prompts */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        padding: '0 2px',
      }}>
        {QUICK_PROMPTS.map((qp) => (
          <button
            key={qp.label}
            onClick={() => sendMessage(qp.prompt)}
            disabled={loading}
            style={{
              padding: '5px 10px',
              fontSize: 12,
              borderRadius: 16,
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.5 : 1,
              transition: 'all 0.15s',
            }}
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* Messages area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '4px 2px',
        minHeight: 0,
      }}>
        {messages.length === 0 && !loading && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            flex: 1,
            gap: 8,
            color: 'rgba(255,255,255,0.3)',
            fontSize: 13,
            textAlign: 'center',
            padding: 20,
          }}>
            <span style={{ fontSize: 28 }}>&#10022;</span>
            <span>Pergunte à IA como melhorar seu roteiro</span>
          </div>
        )}

        {messages.length > 0 && loading && (
          <div className="card p-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Processando resposta da IA...
          </div>
        )}

        {messages.map((msg, msgIdx) => (
          <div
            key={msgIdx}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              gap: 6,
            }}
          >
            {/* Message bubble */}
            <div style={{
              maxWidth: '88%',
              padding: '8px 12px',
              borderRadius: 12,
              fontSize: 13,
              lineHeight: 1.5,
              background: msg.role === 'user'
                ? 'rgba(255,86,56,0.15)'
                : 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: msg.role === 'user'
                ? '1px solid rgba(255,86,56,0.25)'
                : '1px solid rgba(255,255,255,0.06)',
            }}>
              {msg.content}
            </div>

            {/* Suggestions */}
            {msg.suggestions && msg.suggestions.length > 0 && (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                maxWidth: '92%',
              }}>
                {msg.suggestions.map((sug, sugIdx) => {
                  const key = `${msgIdx}-${sugIdx}`
                  const applied = appliedSuggestions.has(key)
                  const applying = applyingKey === key
                  return (
                    <div
                      key={sugIdx}
                      style={{
                        padding: 10,
                        borderRadius: 8,
                        border: '1px solid rgba(255,86,56,0.2)',
                        background: 'var(--bg-raised)',
                      }}
                    >
                      <div style={{
                        fontSize: 11,
                        color: 'var(--color-coral)',
                        fontWeight: 600,
                        marginBottom: 4,
                      }}>
                        Cena {sug.scene_index + 1}
                      </div>
                      <div style={{
                        fontSize: 12,
                        color: 'var(--text-primary)',
                        lineHeight: 1.5,
                        marginBottom: 6,
                      }}>
                        {sug.new_text}
                      </div>
                      <div style={{
                        fontSize: 11,
                        color: 'rgba(255,255,255,0.45)',
                        fontStyle: 'italic',
                        marginBottom: 8,
                      }}>
                        {sug.reason}
                      </div>
                      <button
                        onClick={() => requestApply(msgIdx, sugIdx, sug)}
                        disabled={applied || applying || applyingKey !== null}
                        style={{
                          padding: '4px 14px',
                          fontSize: 12,
                          fontWeight: 600,
                          borderRadius: 6,
                          border: 'none',
                          background: applied ? 'var(--color-mint)' : applying ? 'rgba(255,86,56,0.5)' : 'var(--color-coral)',
                          color: '#fff',
                          cursor: applied || applying ? 'default' : 'pointer',
                          opacity: (applyingKey !== null && !applying) ? 0.5 : 1,
                          transition: 'all 0.15s',
                        }}
                      >
                        {applied ? 'Aplicado' : applying ? 'Regerando narração...' : isPremiumVoice ? 'Aplicar (regrava · 2 créditos)' : 'Aplicar (regenera a narração)'}
                      </button>
                    </div>
                  )
                })}
              {appliedSuggestions.size > 0 && !applyingKey && (
                <div style={{ fontSize: 11, color: 'rgba(16,185,129,0.7)', fontStyle: 'italic', marginTop: 4 }}>
                  Texto e narração atualizados com sucesso.
                </div>
              )}
              </div>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '8px 12px',
            alignSelf: 'flex-start',
          }}>
            <span className="ai-dot ai-dot--1" />
            <span className="ai-dot ai-dot--2" />
            <span className="ai-dot ai-dot--3" />
            <style>{`
              .ai-dot {
                width: 6px; height: 6px; border-radius: 50%;
                background: var(--color-coral); display: inline-block;
                animation: aiBounce 1.2s infinite ease-in-out;
              }
              .ai-dot--2 { animation-delay: 0.15s; }
              .ai-dot--3 { animation-delay: 0.3s; }
              @keyframes aiBounce {
                0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
                40% { opacity: 1; transform: scale(1.1); }
              }
            `}</style>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        display: 'flex',
        gap: 8,
        alignItems: 'flex-end',
      }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Peça melhorias no roteiro..."
          disabled={loading}
          rows={1}
          style={{
            flex: 1,
            padding: '8px 12px',
            fontSize: 13,
            borderRadius: 8,
            border: '1px solid rgba(255,255,255,0.08)',
            background: 'var(--bg-base)',
            color: 'var(--text-primary)',
            resize: 'none',
            outline: 'none',
            fontFamily: 'inherit',
            lineHeight: 1.5,
          }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          style={{
            padding: '8px 14px',
            borderRadius: 8,
            border: 'none',
            background: loading || !input.trim() ? '#333' : 'var(--color-coral)',
            color: loading || !input.trim() ? 'rgba(255,255,255,0.3)' : '#fff',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            fontSize: 13,
            fontWeight: 600,
            transition: 'all 0.15s',
            flexShrink: 0,
          }}
        >
          Enviar
        </button>
      </div>

      {/* Voz premium: aplicar sugestão regrava a narração inteira — custo antes (DESIGN.md) */}
      <Modal open={pendingApply !== null} onClose={() => setPendingApply(null)} labelledBy="apply-modal-titulo">
        <h3 id="apply-modal-titulo" className="text-base font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Aplicar sugestão e regravar a narração?
        </h3>
        <p className="text-sm leading-relaxed mb-1" style={{ color: 'var(--text-secondary)' }}>
          Você está com uma voz premium selecionada: regravar a narração inteira com o texto
          novo custa 2 créditos. Se preferir, aplique só o texto agora e regrave uma única vez
          no final das edições.
        </p>
        <p className="text-xs mb-5" style={{ color: 'var(--text-tertiary)' }}>
          2 créditos{user ? ` · você tem ${user.credits}` : ''}.
        </p>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => pendingApply && handleApply(pendingApply.msgIndex, pendingApply.sugIndex, pendingApply.suggestion, true)}
            className="w-full py-2.5 rounded-lg text-sm font-semibold transition"
            style={{ background: 'var(--color-coral)', color: 'white', border: 'none', cursor: 'pointer' }}
          >
            Aplicar e regravar (2 créditos)
          </button>
          <button
            type="button"
            onClick={() => pendingApply && handleApply(pendingApply.msgIndex, pendingApply.sugIndex, pendingApply.suggestion, false)}
            className="w-full py-2.5 rounded-lg text-sm font-medium transition"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}
          >
            Aplicar só o texto (grátis)
          </button>
          <button
            type="button"
            onClick={() => setPendingApply(null)}
            className="w-full py-2 rounded-lg text-sm font-medium transition"
            style={{ background: 'transparent', color: 'var(--text-secondary)', border: 'none', cursor: 'pointer' }}
          >
            Cancelar
          </button>
        </div>
      </Modal>
    </div>
  )
}

