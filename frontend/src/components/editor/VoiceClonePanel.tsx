'use client'

import { useCallback, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { cloneVoice, deleteVoice, type VoiceInfo } from '@/lib/editor-api'
import { useToast } from '@/components/ui/feedback'
import { useAuth } from '@/contexts/AuthContext'

// AudioRecorder usa MediaRecorder (browser-only) — carrega só no cliente.
const AudioRecorder = dynamic(() => import('./AudioRecorder'), { ssr: false })

const CLONE_CREDIT_COST = 5

interface VoiceClonePanelProps {
  /** Vozes clonadas do usuario (is_clone === true). */
  clones: VoiceInfo[]
  /** Recarrega a lista de vozes apos criar/deletar. */
  onReload: () => Promise<void> | void
  /** Seleciona uma voz clonada para uso na narracao. */
  onSelect: (voice: VoiceInfo) => void
  /** voiceId atualmente selecionado (para highlight). */
  selectedVoiceId?: string
}

export function VoiceClonePanel({ clones, onReload, onSelect, selectedVoiceId }: VoiceClonePanelProps) {
  const { success: toastSuccess, error: toastError } = useToast()
  const { user, refreshUser } = useAuth()
  const [mode, setMode] = useState<'record' | 'file'>('file')
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleRecordingComplete = useCallback((blob: Blob) => {
    setRecordedBlob(blob)
    setFile(null)
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setRecordedBlob(null)
      // Pré-preenche o nome se vazio
      if (!name.trim()) {
        const base = f.name.replace(/\.[^.]+$/, '')
        setName(base.slice(0, 60))
      }
    }
  }

  const handleSubmit = async () => {
    const trimmedName = name.trim()
    if (!trimmedName || submitting) return

    // Monta os arquivos: blob gravado OU file selecionado
    let uploadFile: File | null = null
    if (mode === 'record' && recordedBlob) {
      uploadFile = new File([recordedBlob], 'gravacao.webm', { type: recordedBlob.type || 'audio/webm' })
    } else if (mode === 'file' && file) {
      uploadFile = file
    }
    if (!uploadFile) {
      toastError('Selecione um arquivo', 'Grave ou escolha um áudio de 10 a 30 segundos.')
      return
    }

    setSubmitting(true)
    try {
      const data = await cloneVoice(trimmedName, [uploadFile])
      toastSuccess('Voz clonada!', `"${data.name}" foi criada e já pode ser usada.`)
      // Limpa o form
      setName('')
      setFile(null)
      setRecordedBlob(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      // Atualiza listas e créditos
      await Promise.all([onReload(), refreshUser()])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao clonar voz'
      toastError('Não foi possível clonar a voz', message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (cloneId: string, cloneName: string) => {
    if (deletingId) return
    setDeletingId(cloneId)
    try {
      await deleteVoice(cloneId)
      toastSuccess('Voz removida', `"${cloneName}" foi excluída.`)
      await Promise.all([onReload(), refreshUser()])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao excluir voz'
      toastError('Não foi possível excluir', message)
    } finally {
      setDeletingId(null)
      setConfirmDeleteId(null)
    }
  }

  const hasSample = (mode === 'record' && !!recordedBlob) || (mode === 'file' && !!file)
  const canSubmit = !!name.trim() && hasSample && !submitting
  const reachedLimit = clones.length >= 5

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Lista de clones existentes */}
      {clones.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {clones.filter(c => c.clone_id).map((clone) => {
            const cloneId = clone.clone_id!
            const isSelected = clone.id === selectedVoiceId
            const isConfirming = confirmDeleteId === cloneId
            return (
              <div
                key={cloneId}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 8,
                  background: isSelected ? 'rgba(255,86,56,0.12)' : 'rgba(255,255,255,0.03)',
                  border: isSelected ? '1px solid rgba(255,86,56,0.4)' : '1px solid rgba(255,255,255,0.05)',
                }}
              >
                <button
                  type="button"
                  onClick={() => onSelect(clone)}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left', border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }}
                >
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                    background: isSelected ? 'linear-gradient(135deg,var(--color-coral),var(--color-azure))' : 'rgba(255,255,255,0.05)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12,
                  }}>🎤</div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: isSelected ? '#e2e8f0' : 'rgba(255,255,255,0.65)' }}>
                    {clone.name.replace(' (clone)', '')}
                  </span>
                </button>
                {isConfirming ? (
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      type="button"
                      onClick={() => handleDelete(cloneId, clone.name)}
                      disabled={!!deletingId}
                      style={{
                        padding: '3px 7px', borderRadius: 5, border: 'none', fontSize: 10, fontWeight: 600,
                        background: '#ef4444', color: 'white', cursor: deletingId ? 'not-allowed' : 'pointer',
                        opacity: deletingId ? 0.5 : 1,
                      }}
                    >
                      {deletingId === cloneId ? '...' : 'Confirmar'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteId(null)}
                      style={{
                        padding: '3px 7px', borderRadius: 5, border: '1px solid rgba(255,255,255,0.1)', fontSize: 10,
                        background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)', cursor: 'pointer',
                      }}
                    >Cancelar</button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteId(cloneId)}
                    aria-label={`Excluir ${clone.name}`}
                    style={{
                      width: 26, height: 26, borderRadius: '50%', flexShrink: 0, border: 'none',
                      background: 'rgba(239,68,68,0.1)', color: '#f87171', cursor: 'pointer', fontSize: 12,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >×</button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Formulário de novo clone */}
      {!reachedLimit ? (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 8,
          padding: 12, borderRadius: 10,
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.6)' }}>
            Nova voz clonada <span style={{ fontSize: 9, opacity: 0.5 }}>· custa {CLONE_CREDIT_COST} créditos</span>
          </div>

          {/* Toggle gravar / arquivo */}
          <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.2)', borderRadius: 6, padding: 2 }}>
            <button
              type="button"
              onClick={() => { setMode('file'); setRecordedBlob(null) }}
              style={{
                flex: 1, padding: '5px 0', fontSize: 10, fontWeight: 600, border: 'none', borderRadius: 5,
                cursor: 'pointer',
                background: mode === 'file' ? 'rgba(255,86,56,0.2)' : 'transparent',
                color: mode === 'file' ? 'var(--color-coral-soft)' : 'rgba(255,255,255,0.35)',
              }}
            >Enviar arquivo</button>
            <button
              type="button"
              onClick={() => { setMode('record'); setFile(null); if (fileInputRef.current) fileInputRef.current.value = '' }}
              style={{
                flex: 1, padding: '5px 0', fontSize: 10, fontWeight: 600, border: 'none', borderRadius: 5,
                cursor: 'pointer',
                background: mode === 'record' ? 'rgba(255,86,56,0.2)' : 'transparent',
                color: mode === 'record' ? 'var(--color-coral-soft)' : 'rgba(255,255,255,0.35)',
              }}
            >Gravar</button>
          </div>

          {/* Input de arquivo */}
          {mode === 'file' && (
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/wav,audio/mpeg,audio/mp3,audio/webm,audio/ogg"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                style={{
                  width: '100%', padding: '10px 0', borderRadius: 6, fontSize: 11,
                  border: '1px dashed rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.02)',
                  color: file ? 'var(--color-coral-soft)' : 'rgba(255,255,255,0.4)', cursor: 'pointer',
                }}
              >
                {file ? `✓ ${file.name}` : 'Escolher arquivo (WAV/MP3/WebM)'}
              </button>
            </div>
          )}

          {/* Gravador */}
          {mode === 'record' && (
            <AudioRecorder onRecordingComplete={handleRecordingComplete} maxDuration={30} />
          )}

          <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', lineHeight: 1.4 }}>
            Dica: grave de 10 a 30 segundos em local silencioso, falando de forma natural e pausada.
          </div>

          {/* Nome */}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nome da voz (ex: Minha Voz)"
            maxLength={100}
            style={{
              width: '100%', padding: '7px 10px', fontSize: 12, borderRadius: 6,
              border: '1px solid rgba(255,255,255,0.08)', background: '#1A1A1A', color: '#E8E8E8', outline: 'none',
            }}
          />

          {/* Créditos */}
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>
            <span>Custo: {CLONE_CREDIT_COST} créditos</span>
            {user && <span>Saldo: {user.credits}</span>}
          </div>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            style={{
              padding: '8px 0', border: 'none', borderRadius: 6, color: 'white', fontWeight: 600, fontSize: 12,
              background: submitting ? 'rgba(255,86,56,0.4)' : (canSubmit ? 'var(--color-coral)' : 'rgba(255,86,56,0.25)'),
              cursor: canSubmit ? 'pointer' : 'not-allowed',
            }}
          >
            {submitting ? 'Clonando...' : `Clonar voz (${CLONE_CREDIT_COST} créditos)`}
          </button>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', textAlign: 'center', padding: 12 }}>
          Você atingiu o limite de 5 vozes clonadas. Exclua uma para criar outra.
        </div>
      )}
    </div>
  )
}
