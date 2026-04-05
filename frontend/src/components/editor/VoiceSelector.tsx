'use client'

import { useState } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { getToken } from '@/lib/auth'
import { notifySessionExpired, readApiError } from '@/lib/http'
import { useToast } from '@/components/ui/feedback'

const VOICES = [
  { id: 'pt-BR-AntonioNeural', name: 'Antonio', gender: 'M', desc: 'Masculina natural, amigavel', tag: 'Popular' },
  { id: 'pt-BR-FranciscaNeural', name: 'Francisca', gender: 'F', desc: 'Feminina clara, versatil', tag: 'Versatil' },
]

export function VoiceSelector() {
  const { composition, updateVoiceConfig, updateAudio, jobId } = useEditor()
  const { error: toastError } = useToast()
  const [regenerating, setRegenerating] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)

  if (!composition) return null

  const { voiceConfig } = composition

  const handleRegenerate = async () => {
    if (!composition || regenerating) return
    setRegenerating(true)
    setRegenError(null)
    try {
      const token = getToken()
      const res = await fetch(`/api/v1/jobs/${jobId}/regenerate-tts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          text: composition.scenes.map(s => s.text).join(' '),
          voice_id: voiceConfig.voiceId,
          rate: voiceConfig.rate,
          pitch: voiceConfig.pitch,
        }),
      })
      if (res.status === 401) notifySessionExpired()
      if (!res.ok) throw new Error(await readApiError(res, 'Falha ao regerar narração'))
      const data = await res.json()
      // Append timestamp to bust browser audio cache
      const audioUrl = `${data.audio_url}?t=${Date.now()}`
      updateAudio(data.words, audioUrl)
    } catch (err) {
      console.error('Regeneration failed:', err)
      const message = err instanceof Error ? err.message : 'Erro desconhecido'
      setRegenError(message)
      toastError('Não foi possível regerar a narração', message)
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="editor-section-header">Voz da narração</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {VOICES.map((v) => {
          const isSelected = v.id === voiceConfig.voiceId
          return (
            <button
              key={v.id}
              onClick={() => updateVoiceConfig({ voiceId: v.id })}
              className={`editor-card ${isSelected ? 'editor-card--selected' : ''}`}
              style={{ cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 8, border: 'none' }}
            >
              <div style={{
                width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                background: isSelected ? 'linear-gradient(135deg,#7c3aed,#3b82f6)' : 'rgba(255,255,255,0.05)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
              }}>
                {v.gender === 'M' ? '♂' : '♀'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: isSelected ? '#e2e8f0' : 'rgba(255,255,255,0.55)' }}>{v.name}</span>
                  <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: 'rgba(124,58,237,0.12)', color: '#c4b5fd' }}>{v.tag}</span>
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 1 }}>{v.desc}</div>
              </div>
            </button>
          )
        })}
      </div>

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

      <button
        onClick={handleRegenerate}
        disabled={regenerating}
        style={{
          padding: '9px 0',
          background: regenerating ? 'rgba(124,58,237,0.4)' : 'linear-gradient(135deg,#7c3aed,#3b82f6)',
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
