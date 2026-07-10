'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { MessageSquare, Star, X } from 'lucide-react'

import { submitFeedback } from '@/lib/feedback'
import { useToast } from '@/components/ui/feedback'

/**
 * Botão flutuante de feedback (beta): abre painel com nota 1-5 + comentário opcional.
 * Só abre por clique — nunca popup automático. bottom-20 no mobile deixa a
 * MobileBottomNav livre; z-[60] fica abaixo dos toasts (z-[80]) e do player (z-[90]).
 */
export default function FeedbackWidget() {
  const pathname = usePathname()
  const { success, error: toastError } = useToast()
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState(0)
  const [hovered, setHovered] = useState(0)
  const [comment, setComment] = useState('')
  const [sending, setSending] = useState(false)

  async function handleSubmit() {
    if (rating === 0 && !comment.trim()) {
      toastError('Feedback vazio', 'Escolha uma nota ou escreva um comentário.')
      return
    }
    setSending(true)
    try {
      await submitFeedback({
        kind: 'widget',
        rating: rating || undefined,
        comment: comment.trim() || undefined,
        source_url: pathname ?? undefined,
      })
      success('Feedback enviado', 'Obrigado por ajudar a melhorar o ClipIA! 💛')
      setOpen(false)
      setRating(0)
      setComment('')
    } catch (err) {
      toastError('Falha ao enviar', err instanceof Error ? err.message : 'Tente novamente.')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed bottom-36 right-4 z-[60] w-[min(20rem,calc(100vw-2rem))] rounded-2xl border p-4 shadow-2xl md:bottom-20"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          role="dialog"
          aria-label="Enviar feedback"
        >
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Como está sua experiência?
            </p>
            <button
              onClick={() => setOpen(false)}
              aria-label="Fechar feedback"
              className="rounded-lg p-1 transition hover:bg-white/10"
              style={{ color: 'var(--text-secondary)' }}
            >
              <X size={14} />
            </button>
          </div>

          <div className="mt-3 flex justify-center gap-1" onMouseLeave={() => setHovered(0)}>
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                onClick={() => setRating(value)}
                onMouseEnter={() => setHovered(value)}
                aria-label={`Nota ${value}`}
                className="p-1 transition-transform hover:scale-110"
              >
                <Star
                  size={22}
                  fill={(hovered || rating) >= value ? '#fbbf24' : 'transparent'}
                  color={(hovered || rating) >= value ? '#fbbf24' : 'var(--text-tertiary)'}
                />
              </button>
            ))}
          </div>

          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            maxLength={1000}
            rows={3}
            placeholder="O que podemos melhorar? (opcional)"
            className="mt-3 w-full resize-none rounded-xl px-3 py-2 text-sm outline-none"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
            }}
          />

          <button
            onClick={() => void handleSubmit()}
            disabled={sending}
            className="mt-3 w-full rounded-xl py-2.5 text-sm font-semibold transition disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #ff5638, #3e9bff)', color: '#fff' }}
          >
            {sending ? 'Enviando…' : 'Enviar feedback'}
          </button>
        </div>
      )}

      <button
        onClick={() => setOpen((value) => !value)}
        aria-label="Enviar feedback"
        aria-expanded={open}
        className="fixed bottom-20 right-4 z-[60] flex h-11 w-11 items-center justify-center rounded-full shadow-lg transition hover:scale-105 md:bottom-6"
        style={{ background: 'linear-gradient(135deg, #ff5638, #3e9bff)', color: '#fff' }}
      >
        <MessageSquare size={18} />
      </button>
    </>
  )
}
