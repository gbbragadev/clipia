'use client'

import { useCallback, useEffect, useState } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'
import { fetchVoices, type VoiceInfo } from '@/lib/editor-api'
import { useToast } from '@/components/ui/feedback'

type Tab = 'free' | 'premium' | 'custom'

const TAB_LABELS: Record<Tab, string> = {
  free: 'Grátis',
  premium: 'Premium',
  custom: 'Minha Voz',
}

const TAB_BADGES: Record<Tab, string> = {
  free: '',
  premium: '2 créditos',
  custom: '1 crédito',
}

export function VoiceSelector() {
  const { composition, updateVoiceConfig, updateAudio, jobId } = useEditor()
  const { error: toastError } = useToast()
  const [regenerating, setRegenerating] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('free')
  const [voices, setVoices] = useState<VoiceInfo[]>([])
  const [loadingVoices, setLoadingVoices] = useState(false)
  const [previewPlaying, setPreviewPlaying] = useState<string | null>(null)

  const loadVoices = useCallback(async () => {
    setLoadingVoices(true)
    try {
      const data = await fetchVoices()
      setVoices(data)
    } catch {
      // Fallback to Edge voices
    } finally {
      setLoadingVoices(false)
    }
  }, [])

  useEffect(() => { loadVoices() }, [loadVoices])

  if (!composition) return null

  const { voiceConfig } = composition

  const edgeVoices = voices.filter(v => v.provider === 'edge')
  const elevenVoices = voices.filter(v => v.provider === 'elevenlabs')

  const handleVoiceSelect = (voice: VoiceInfo) => {
    updateVoiceConfig({
      voiceId: voice.id,
      voiceProvider: voice.provider,
    })
  }

  const handlePreview = (voice: VoiceInfo) => {
    if (!voice.preview_url) return
    if (previewPlaying === voice.id) {
      setPreviewPlaying(null)
      return
    }
    setPreviewPlaying(voice.id)
    const audio = new Audio(voice.preview_url)
    audio.onended = () => setPreviewPlaying(null)
    audio.onerror = () => setPreviewPlaying(null)
    audio.play().catch(() => setPreviewPlaying(null))
  }

  const handleRegenerate = async () => {
    if (!composition || regenerating) return
    setRegenerating(true)
    setRegenError(null)
    try {
      const token = getToken()
      const provider = voiceConfig.voiceProvider || 'edge'
      const res = await fetch(`/api/v1/jobs/${jobId}/regenerate-tts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          text: composition.scenes.map(s => s.text).join(' '),
          voice_id: voiceConfig.voiceId,
          voice_provider: provider,
          rate: voiceConfig.rate,
          pitch: voiceConfig.pitch,
        }),
      })
      if (!res.ok) throw new Error(await readApiError(res, 'Falha ao regerar narração'))
      const data = await res.json()
      const audioUrl = `${data.audio_url}?t=${Date.now()}`
      updateAudio(data.words, audioUrl)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro desconhecido'
      setRegenError(message)
      toastError('Não foi possível regerar a narração', message)
    } finally {
      setRegenerating(false)
    }
  }

  const renderVoiceCard = (v: VoiceInfo) => {
    const isSelected = v.id === voiceConfig.voiceId
    return (
      <button
        key={v.id}
        onClick={() => handleVoiceSelect(v)}
        className={`editor-card ${isSelected ? 'editor-card--selected' : ''}`}
        style={{ cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 8, border: 'none' }}
      >
        <div style={{
          width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
          background: isSelected ? 'linear-gradient(135deg,var(--color-coral),var(--color-azure))' : 'rgba(255,255,255,0.05)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
        }}>
          {v.is_clone ? '🎤' : v.gender === 'male' ? '♂' : v.gender === 'female' ? '♀' : '🔊'}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: isSelected ? '#e2e8f0' : 'rgba(255,255,255,0.55)' }}>{v.name}</span>
            {v.is_clone && (
              <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: 'rgba(62,155,255,0.15)', color: 'var(--color-azure)' }}>Clonada</span>
            )}
          </div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 1 }}>{v.language}</div>
        </div>
        {v.preview_url && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handlePreview(v) }}
            style={{
              width: 24, height: 24, borderRadius: '50%', border: 'none', flexShrink: 0,
              background: previewPlaying === v.id ? 'rgba(255,86,56,0.3)' : 'rgba(255,255,255,0.05)',
              color: previewPlaying === v.id ? 'var(--color-coral-soft)' : 'rgba(255,255,255,0.3)',
              cursor: 'pointer', fontSize: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            {previewPlaying === v.id ? '■' : '▶'}
          </button>
        )}
      </button>
    )
  }

  const isEdgeProvider = !voiceConfig.voiceProvider || voiceConfig.voiceProvider === 'edge'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="editor-section-header">Voz da narração</div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 2 }}>
        {(Object.keys(TAB_LABELS) as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              flex: 1, padding: '6px 0', fontSize: 11, fontWeight: 600, border: 'none', borderRadius: 6,
              cursor: 'pointer', transition: 'all 0.15s',
              background: activeTab === tab ? 'rgba(255,86,56,0.2)' : 'transparent',
              color: activeTab === tab ? 'var(--color-coral-soft)' : 'rgba(255,255,255,0.35)',
            }}
          >
            {TAB_LABELS[tab]}
            {TAB_BADGES[tab] && (
              <span style={{ display: 'block', fontSize: 8, opacity: 0.6, marginTop: 1 }}>
                {TAB_BADGES[tab]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Voice List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minHeight: 80 }}>
        {loadingVoices ? (
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', textAlign: 'center', padding: 16 }}>
            Carregando vozes...
          </div>
        ) : activeTab === 'free' ? (
          edgeVoices.length > 0 ? edgeVoices.map(renderVoiceCard) : (
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', textAlign: 'center', padding: 16 }}>
              Nenhuma voz gratuita disponível
            </div>
          )
        ) : activeTab === 'premium' ? (
          elevenVoices.length > 0 ? elevenVoices.map(renderVoiceCard) : (
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', textAlign: 'center', padding: 16 }}>
              Vozes premium em breve
            </div>
          )
        ) : (
          /* Custom tab — upload/record placeholder */
          <div style={{ textAlign: 'center', padding: '16px 8px' }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>🎙️</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 4 }}>
              Grave ou envie seu áudio
            </div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>
              Use a aba &quot;Minha Voz&quot; no gerador para enviar seu áudio personalizado
            </div>
          </div>
        )}
      </div>

      {/* Rate/Pitch sliders — only for Edge voices */}
      {isEdgeProvider && (
        <>
          <div>
            <div className="editor-section-header">Velocidade &middot; {voiceConfig.rate > 0 ? '+' : ''}{voiceConfig.rate}%</div>
            <input type="range" className="editor-slider" min={-30} max={30} value={voiceConfig.rate}
              onChange={(e) => updateVoiceConfig({ rate: Number(e.target.value) })} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'rgba(255,255,255,0.2)', marginTop: 3 }}>
              <span>Lento</span><span>Normal</span><span>Rapido</span>
            </div>
          </div>

          <div>
            <div className="editor-section-header">Tom &middot; {voiceConfig.pitch > 0 ? '+' : ''}{voiceConfig.pitch}Hz</div>
            <input type="range" className="editor-slider" min={-10} max={10} value={voiceConfig.pitch}
              onChange={(e) => updateVoiceConfig({ pitch: Number(e.target.value) })} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'rgba(255,255,255,0.2)', marginTop: 3 }}>
              <span>Grave</span><span>Normal</span><span>Agudo</span>
            </div>
          </div>
        </>
      )}

      <button
        onClick={handleRegenerate}
        disabled={regenerating}
        style={{
          padding: '9px 0',
          background: regenerating ? 'rgba(255,86,56,0.4)' : 'linear-gradient(135deg,var(--color-coral),var(--color-azure))',
          border: 'none', borderRadius: 7, color: 'white', fontWeight: 600, fontSize: 12,
          cursor: regenerating ? 'not-allowed' : 'pointer',
          opacity: regenerating ? 0.7 : 1,
        }}
      >
        {regenerating ? 'Regerando...' : 'Regerar narração'}
      </button>
      {regenError && (
        <div style={{ fontSize: 10, color: '#f87171', marginTop: -8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span>{regenError}</span>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={regenerating}
            style={{
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 999,
              padding: '4px 8px',
              background: 'rgba(255,255,255,0.04)',
              color: '#fff',
              fontSize: 10,
              cursor: regenerating ? 'not-allowed' : 'pointer',
            }}
          >
            Tentar novamente
          </button>
        </div>
      )}
    </div>
  )
}
