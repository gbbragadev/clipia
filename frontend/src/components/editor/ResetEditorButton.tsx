'use client'

import { useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { resetJob } from '@/lib/editor-api'
import { useToast } from '@/components/ui/feedback'
import { useAuth } from '@/contexts/AuthContext'

/**
 * Botão "Resetar edição" para o editor.
 *
 * O reset do backend (POST /jobs/{id}/reset) custa 1 credito, zera
 * pending_credits e limpa o editor_state (volta ao default pre-edicao).
 * Como o editor_state e limpo no servidor, recarregamos a pagina para
 * que o EditorContext busque a composicao nova (sem o estado salvo).
 */
export function ResetEditorButton({ jobId }: { jobId: string }) {
  const { success: toastSuccess, error: toastError } = useToast()
  const { refreshUser } = useAuth()
  const [confirming, setConfirming] = useState(false)
  const [resetting, setResetting] = useState(false)

  const handleReset = async () => {
    if (resetting) return
    setResetting(true)
    try {
      await resetJob(jobId)
      toastSuccess('Edição resetada', 'As alterações foram descartadas. Crédito de 1 debitado.')
      await refreshUser()
      // editor_state foi limpo no backend — recarrega para buscar o estado default.
      window.location.reload()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Não foi possível resetar a edição'
      toastError('Não foi possível resetar', message)
      setResetting(false)
      setConfirming(false)
    }
  }

  if (confirming) {
    return (
      <div className="editor-header__reset-confirm" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>Resetar? Custa 1 crédito.</span>
        <button
          type="button"
          onClick={handleReset}
          disabled={resetting}
          className="editor-btn-sm"
          style={{
            background: 'rgba(239,68,68,0.2)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.3)',
            cursor: resetting ? 'not-allowed' : 'pointer', opacity: resetting ? 0.5 : 1,
          }}
        >
          {resetting ? 'Resetando...' : 'Confirmar'}
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          disabled={resetting}
          className="editor-btn-sm"
          style={{ cursor: resetting ? 'not-allowed' : 'pointer' }}
        >
          Cancelar
        </button>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => setConfirming(true)}
      className="editor-btn-sm inline-flex items-center gap-1.5"
      title="Volta o vídeo ao estado pré-edição (custa 1 crédito)"
      style={{ whiteSpace: 'nowrap' }}
    >
      <RotateCcw className="w-3.5 h-3.5" /> Resetar
    </button>
  )
}
