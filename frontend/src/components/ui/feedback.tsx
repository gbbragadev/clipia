'use client'

import Link from 'next/link'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

export type ToastTone = 'success' | 'error' | 'info'

export interface ToastInput {
  title: string
  description?: string
  tone?: ToastTone
  actionLabel?: string
  onAction?: () => void
  durationMs?: number
}

interface ToastItem extends Required<Pick<ToastInput, 'title'>> {
  id: string
  description?: string
  tone: ToastTone
  actionLabel?: string
  onAction?: () => void
}

interface ToastContextValue {
  toast: (input: ToastInput) => string
  success: (title: string, description?: string) => string
  error: (title: string, description?: string) => string
  info: (title: string, description?: string) => string
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

function useStableId() {
  return useCallback(() => {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID()
    }
    return `toast_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  }, [])
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timeouts = useRef(new Map<string, ReturnType<typeof setTimeout>>())
  const createId = useStableId()

  const dismiss = useCallback((id: string) => {
    const timeout = timeouts.current.get(id)
    if (timeout) {
      clearTimeout(timeout)
      timeouts.current.delete(id)
    }
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const toast = useCallback((input: ToastInput) => {
    const id = createId()
    const item: ToastItem = {
      id,
      title: input.title,
      description: input.description,
      tone: input.tone ?? 'info',
      actionLabel: input.actionLabel,
      onAction: input.onAction,
    }

    setToasts((current) => [item, ...current].slice(0, 4))

    const timeoutMs = input.durationMs ?? 5000
    timeouts.current.set(id, setTimeout(() => dismiss(id), timeoutMs))
    return id
  }, [createId, dismiss])

  const api = useMemo<ToastContextValue>(() => ({
    toast,
    success: (title, description) => toast({ title, description, tone: 'success' }),
    error: (title, description) => toast({ title, description, tone: 'error', durationMs: 6500 }),
    info: (title, description) => toast({ title, description, tone: 'info' }),
    dismiss,
  }), [dismiss, toast])

  useEffect(() => {
    return () => {
      for (const timeout of timeouts.current.values()) clearTimeout(timeout)
      timeouts.current.clear()
    }
  }, [])

  return (
    <ToastContext value={api}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export function ToastViewport({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed right-4 top-4 z-[80] w-[min(24rem,calc(100vw-2rem))] space-y-3">
      {toasts.map((toast) => {
        const palette = TOAST_PALETTE[toast.tone]
        return (
          <div
            key={toast.id}
            className="card overflow-hidden shadow-2xl"
            style={{
              background: palette.bg,
              borderColor: palette.border,
            }}
          >
            <div className="flex items-start gap-3 p-4">
              <div
                className="mt-0.5 h-2.5 w-2.5 rounded-full shrink-0"
                style={{ background: palette.dot }}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {toast.title}
                </p>
                {toast.description && (
                  <p className="mt-1 text-sm leading-5" style={{ color: 'var(--text-secondary)' }}>
                    {toast.description}
                  </p>
                )}
                {(toast.actionLabel || toast.onAction) && (
                  <div className="mt-3 flex items-center gap-3">
                    {toast.onAction && toast.actionLabel && (
                      <button
                        onClick={() => {
                          toast.onAction?.()
                          onDismiss(toast.id)
                        }}
                        className="text-sm font-medium"
                        style={{ color: palette.action }}
                      >
                        {toast.actionLabel}
                      </button>
                    )}
                    <button
                      onClick={() => onDismiss(toast.id)}
                      className="text-sm"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      Fechar
                    </button>
                  </div>
                )}
              </div>
              <button
                onClick={() => onDismiss(toast.id)}
                className="text-lg leading-none transition hover:opacity-80"
                style={{ color: 'var(--text-tertiary)' }}
                aria-label="Fechar aviso"
              >
                ×
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}

const TOAST_PALETTE: Record<ToastTone, { bg: string; border: string; dot: string; action: string }> = {
  success: {
    bg: 'rgba(34, 197, 94, 0.12)',
    border: 'rgba(34, 197, 94, 0.28)',
    dot: '#22c55e',
    action: '#86efac',
  },
  error: {
    bg: 'rgba(239, 68, 68, 0.12)',
    border: 'rgba(239, 68, 68, 0.28)',
    dot: '#ef4444',
    action: '#fca5a5',
  },
  info: {
    bg: 'rgba(59, 130, 246, 0.12)',
    border: 'rgba(59, 130, 246, 0.24)',
    dot: '#3b82f6',
    action: '#93c5fd',
  },
}

export function OfflineBanner({ online }: { online: boolean }) {
  if (online) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-[70] flex justify-center px-4">
      <div
        className="pointer-events-auto rounded-full border px-4 py-2 text-sm shadow-lg backdrop-blur-md"
        style={{
          background: 'rgba(17, 17, 24, 0.9)',
          borderColor: 'rgba(239, 68, 68, 0.3)',
          color: '#fecaca',
        }}
      >
        Voce esta offline. Alguns recursos podem falhar ate a conexao voltar.
      </div>
    </div>
  )
}

export function InlineError({
  title,
  description,
  onRetry,
  retryLabel = 'Tentar novamente',
}: {
  title: string
  description?: string
  onRetry?: () => void
  retryLabel?: string
}) {
  return (
    <div className="card p-5">
      <div className="flex flex-col gap-3">
        <div>
          <p className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            {title}
          </p>
          {description && (
            <p className="mt-1 text-sm leading-5" style={{ color: 'var(--text-secondary)' }}>
              {description}
            </p>
          )}
        </div>
        {onRetry && (
          <button className="btn-primary self-start px-4 py-2 text-sm" onClick={onRetry}>
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  )
}

export function RouteErrorScreen({
  title,
  description,
  onRetry,
  homeHref = '/',
  homeLabel = 'Voltar para a home',
}: {
  title: string
  description: string
  onRetry: () => void
  homeHref?: string
  homeLabel?: string
}) {
  return (
    <main className="min-h-screen px-4 py-16 flex items-center justify-center">
      <div className="card w-full max-w-xl p-8 text-center">
        <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl" style={{ background: 'rgba(124, 58, 237, 0.12)' }}>
          <span className="text-2xl">!</span>
        </div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h1>
        <p className="mt-3 text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
          {description}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <button onClick={onRetry} className="btn-primary px-4 py-2">
            Tentar novamente
          </button>
          <Link href={homeHref} className="btn-outline px-4 py-2">
            {homeLabel}
          </Link>
        </div>
      </div>
    </main>
  )
}

export function NotFoundScreen() {
  return (
    <main className="min-h-screen px-4 py-16 flex items-center justify-center">
      <div className="card w-full max-w-xl p-8 text-center">
        <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl" style={{ background: 'rgba(59, 130, 246, 0.12)' }}>
          <span className="text-2xl">404</span>
        </div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Página não encontrada
        </h1>
        <p className="mt-3 text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
          O endereço solicitado não existe ou foi movido.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/" className="btn-primary px-4 py-2">
            Ir para a home
          </Link>
          <Link href="/dashboard" className="btn-outline px-4 py-2">
            Abrir dashboard
          </Link>
        </div>
      </div>
    </main>
  )
}
