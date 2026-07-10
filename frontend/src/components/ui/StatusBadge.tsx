import { cn } from '@/components/landing/utils/cn'

/** Badge de status semântico — labels SEMPRE pt-BR, cores SEMPRE dos tokens.
 * Fonte de verdade visual: frontend/DESIGN.md (guardrail: status honesto e legível). */

export type BadgeVariant = 'success' | 'danger' | 'warn' | 'info' | 'neutral' | 'processing'

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  success: 'bg-success/15 text-success border-success/30',
  danger: 'bg-danger/15 text-danger border-danger/30',
  warn: 'bg-warn/15 text-warn border-warn/30',
  info: 'bg-azure/15 text-azure border-azure/30',
  neutral: 'bg-white/8 text-mist border-white/10',
  processing: 'bg-coral/15 text-coral border-coral/30 animate-pulse',
}

export function StatusBadge({
  variant,
  children,
  className,
}: {
  variant: BadgeVariant
  children: React.ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
        VARIANT_CLASSES[variant],
        className
      )}
    >
      {children}
    </span>
  )
}

/** Status de job (pipeline de geração) → variante + label pt-BR. */
export function jobStatusBadge(status: string): { variant: BadgeVariant; label: string } {
  switch (status) {
    case 'completed':
    case 'editable':
      return { variant: 'success', label: 'Pronto' }
    case 'failed':
    case 'error':
      return { variant: 'danger', label: 'Erro' }
    case 'rendering':
      return { variant: 'info', label: 'Atualizando' }
    case 'queued':
      return { variant: 'neutral', label: 'Na fila' }
    case 'cancelling':
      return { variant: 'neutral', label: 'Cancelando' }
    case 'cancelled':
      return { variant: 'neutral', label: 'Cancelado' }
    default:
      return { variant: 'processing', label: 'Gerando' }
  }
}

/** Status de compra (Mercado Pago/Stripe) → variante + label pt-BR. */
export function purchaseStatusBadge(status: string): { variant: BadgeVariant; label: string } {
  switch (status) {
    case 'approved':
      return { variant: 'success', label: 'Aprovado' }
    case 'pending':
      return { variant: 'warn', label: 'Pendente' }
    case 'refunded':
      return { variant: 'neutral', label: 'Estornado' }
    case 'rejected':
    case 'failed':
      return { variant: 'danger', label: 'Recusado' }
    default:
      return { variant: 'neutral', label: status }
  }
}
