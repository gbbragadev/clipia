'use client'

import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { cn } from '@/components/landing/utils/cn'
import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'

/** Modal acessível padrão do app: portal + role=dialog + Esc + clique-fora +
 * foco inicial no painel e devolução do foco ao fechar. Use para QUALQUER
 * confirmação — especialmente ações pagas ou destrutivas (DESIGN.md). */
export function Modal({
  open,
  onClose,
  labelledBy,
  children,
  className,
}: {
  open: boolean
  onClose: () => void
  /** id do heading dentro do modal (aria-labelledby) */
  labelledBy?: string
  children: ReactNode
  className?: string
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocus = useRef<HTMLElement | null>(null)
  const reduceMotion = useReducedMotionState()

  useEffect(() => {
    if (!open) return
    previousFocus.current = document.activeElement as HTMLElement | null
    panelRef.current?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      // Focus trap: Tab/Shift+Tab ciclam DENTRO do painel — sem isso, teclado/leitor
      // de tela atravessava o modal e acionava a página atrás (inclusive em ações pagas).
      if (e.key === 'Tab' && panelRef.current) {
        const focusables = panelRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (focusables.length === 0) {
          e.preventDefault()
          return
        }
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        const active = document.activeElement
        if (e.shiftKey && (active === first || active === panelRef.current)) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && active === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      previousFocus.current?.focus?.()
    }
  }, [open, onClose])

  if (typeof document === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="modal-overlay"
          className="fixed inset-0 z-[90] flex items-center justify-center p-4"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: DURATIONS.fast, ease: EASE }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onClose()
          }}
          style={{ background: 'var(--overlay-bg)' }}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy}
            tabIndex={-1}
            initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: DURATIONS.fast, ease: EASE }}
            className={cn(
              'w-full max-w-sm rounded-2xl border border-white/10 bg-[var(--bg-raised)] p-6 shadow-2xl outline-none',
              className
            )}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  )
}
