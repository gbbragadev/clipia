'use client'

import { useRef, useState, useEffect } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'
import { useToast } from '@/components/ui/feedback'

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
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [appliedSuggestions, setAppliedSuggestions] = useState<Set<string>>(new Set())
  const [applyingKey, setApplyingKey] = useState<string | null>(null)
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

  const handleApply = async (msgIndex: number, sugIndex: number, suggestion: Suggestion) => {
    if (!composition) return
    const key = `${msgIndex}-${sugIndex}`
    setApplyingKey(key)

    // 1. Update scene text in composition state
    updateScene(suggestion.scene_index, { text: suggestion.new_text })

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
          rate: composition.voiceConfig?.rate ?? -10,
          pitch: composition.voiceConfig?.pitch ?? 5,
        }),
      })
      if (!res.ok) throw new Error(await readApiError(res, 'Falha ao regerar narração'))
      const data = await res.json()
      const audioUrl = `${data.audio_url}?t=${Date.now()}`
      updateAudio(data.words, audioUrl)
      setAppliedSuggestions(prev => new Set(prev).add(key))
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
              background: '#2A2A2A',
              color: '#ccc',
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
            <span>Pergunte a IA como melhorar seu roteiro</span>
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
                ? 'rgba(108,92,231,0.15)'
                : '#2A2A2A',
              color: '#E8E8E8',
              border: msg.role === 'user'
                ? '1px solid rgba(108,92,231,0.25)'
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
                        border: '1px solid rgba(108,92,231,0.2)',
                        background: '#252525',
                      }}
                    >
                      <div style={{
                        fontSize: 11,
                        color: '#6C5CE7',
                        fontWeight: 600,
                        marginBottom: 4,
                      }}>
                        Cena {sug.scene_index + 1}
                      </div>
                      <div style={{
                        fontSize: 12,
                        color: '#E8E8E8',
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
                        onClick={() => handleApply(msgIdx, sugIdx, sug)}
                        disabled={applied || applying || applyingKey !== null}
                        style={{
                          padding: '4px 14px',
                          fontSize: 12,
                          fontWeight: 600,
                          borderRadius: 6,
                          border: 'none',
                          background: applied ? '#10b981' : applying ? 'rgba(108,92,231,0.5)' : '#6C5CE7',
                          color: '#fff',
                          cursor: applied || applying ? 'default' : 'pointer',
                          opacity: (applyingKey !== null && !applying) ? 0.5 : 1,
                          transition: 'all 0.15s',
                        }}
                      >
                        {applied ? 'Aplicado' : applying ? 'Regerando narracao...' : 'Aplicar'}
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
                background: #6C5CE7; display: inline-block;
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
          placeholder="Peca melhorias no roteiro..."
          disabled={loading}
          rows={1}
          style={{
            flex: 1,
            padding: '8px 12px',
            fontSize: 13,
            borderRadius: 8,
            border: '1px solid rgba(255,255,255,0.08)',
            background: '#1A1A1A',
            color: '#E8E8E8',
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
            background: loading || !input.trim() ? '#333' : '#6C5CE7',
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
    </div>
  )
}

