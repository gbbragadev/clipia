'use client'

import { useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { resetJob } from '@/lib/editor-api'
import { useToast } from '@/components/ui/feedback'
import { Modal } from '@/components/ui/Modal'
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
  const { user, refreshUser } = useAuth()
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

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="editor-btn-sm inline-flex items-center gap-1.5"
        title="Volta o vídeo ao estado pré-edição (custa 1 crédito)"
        style={{ whiteSpace: 'nowrap' }}
      >
        <RotateCcw className="w-3.5 h-3.5" /> <span className="editor-header__reset-label">Resetar</span>
      </button>

      {/* Ação paga E destrutiva: consequência + custo explícitos antes de confirmar (DESIGN.md) */}
      <Modal open={confirming} onClose={() => { if (!resetting) setConfirming(false) }} labelledBy="reset-modal-titulo">
        <h3 id="reset-modal-titulo" className="text-base font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Resetar a edição?
        </h3>
        <p className="text-sm leading-relaxed mb-1" style={{ color: 'var(--text-secondary)' }}>
          Todas as edições feitas neste vídeo serão descartadas e ele volta ao estado
          original da geração. Essa ação não pode ser desfeita.
        </p>
        <p className="text-xs mb-5" style={{ color: 'var(--text-tertiary)' }}>
          Custa 1 crédito{user ? ` · você tem ${user.credits}` : ''}.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={resetting}
            className="flex-1 py-2.5 rounded-lg text-sm font-semibold transition"
            style={{
              background: 'rgba(248,113,113,0.15)', color: 'var(--color-danger)',
              border: '1px solid rgba(248,113,113,0.3)',
              cursor: resetting ? 'not-allowed' : 'pointer', opacity: resetting ? 0.6 : 1,
            }}
          >
            {resetting ? 'Resetando...' : 'Resetar (1 crédito)'}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            disabled={resetting}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium transition"
            style={{
              background: 'var(--bg-surface)', color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: resetting ? 'not-allowed' : 'pointer',
            }}
          >
            Manter edição
          </button>
        </div>
      </Modal>
    </>
  )
}
