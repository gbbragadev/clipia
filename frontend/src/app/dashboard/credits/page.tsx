'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { ApiError } from '@/lib/http'
import {
  createCheckout,
  fetchCheckoutStatus,
  fetchPackages,
  type CheckoutCreationResult,
  type CheckoutStatus,
  type CreditPackage,
  type PaymentProvider,
} from '@/lib/payments'
import {
  apiIdToSelectedPackage,
  parseSelectedPackage,
  selectedPackageLabel,
  type SelectedPackage,
} from '@/lib/package-intent'
import CreditPackageCard from '@/components/dashboard/CreditPackageCard'
import PurchaseHistory from '@/components/dashboard/PurchaseHistory'
import { InlineError } from '@/components/ui/feedback'
import { useToast } from '@/components/ui/feedback'
import { trackProductEvent } from '@/lib/analytics'

const CHECKOUT_ATTEMPT_STORAGE_KEY = 'clipia_checkout_attempt'
const CHECKOUT_POLL_DELAYS_MS = [250, 500, 1_000, 2_000] as const
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

interface StoredCheckoutAttempt {
  version: 1
  fingerprint: string
  idempotency_key: string
  purchase_id?: string
}

function isStoredCheckoutAttempt(value: unknown): value is StoredCheckoutAttempt {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const candidate = value as Partial<StoredCheckoutAttempt>
  return (
    candidate.version === 1 &&
    typeof candidate.fingerprint === 'string' &&
    typeof candidate.idempotency_key === 'string' &&
    UUID_PATTERN.test(candidate.idempotency_key) &&
    (candidate.purchase_id === undefined ||
      (typeof candidate.purchase_id === 'string' && UUID_PATTERN.test(candidate.purchase_id)))
  )
}

function writeCheckoutAttempt(attempt: StoredCheckoutAttempt): void {
  window.sessionStorage.setItem(CHECKOUT_ATTEMPT_STORAGE_KEY, JSON.stringify(attempt))
}

function createIdempotencyKey(): string {
  if (typeof crypto === 'undefined' || typeof crypto.randomUUID !== 'function') {
    throw new Error('Seu navegador não oferece geração segura para iniciar o checkout.')
  }
  return crypto.randomUUID()
}

function getOrCreateCheckoutAttempt(fingerprint: string): StoredCheckoutAttempt {
  const raw = window.sessionStorage.getItem(CHECKOUT_ATTEMPT_STORAGE_KEY)
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw)
      if (isStoredCheckoutAttempt(parsed) && parsed.fingerprint === fingerprint) return parsed
    } catch {
      // Uma tentativa local corrompida não pode orientar uma nova compra.
    }
  }

  const attempt: StoredCheckoutAttempt = {
    version: 1,
    fingerprint,
    idempotency_key: createIdempotencyKey(),
  }
  writeCheckoutAttempt(attempt)
  return attempt
}

function clearCheckoutAttempt(expected: StoredCheckoutAttempt): void {
  const raw = window.sessionStorage.getItem(CHECKOUT_ATTEMPT_STORAGE_KEY)
  if (!raw) return
  try {
    const current: unknown = JSON.parse(raw)
    if (
      isStoredCheckoutAttempt(current) &&
      current.fingerprint === expected.fingerprint &&
      current.idempotency_key === expected.idempotency_key
    ) {
      window.sessionStorage.removeItem(CHECKOUT_ATTEMPT_STORAGE_KEY)
    }
  } catch {
    window.sessionStorage.removeItem(CHECKOUT_ATTEMPT_STORAGE_KEY)
  }
}

export default function CreditsPage() {
  const { user, refreshUser } = useAuth()
  const { success, error, info } = useToast()
  const searchParams = useSearchParams()
  const [packages, setPackages] = useState<CreditPackage[]>([])
  const [loadingPackages, setLoadingPackages] = useState(true)
  const [packagesError, setPackagesError] = useState<string | null>(null)
  // Pix (Mercado Pago) como default — e o preferido no BR e o caminho mais rapido/barato.
  const [provider, setProvider] = useState<PaymentProvider>('mercadopago')
  const [selectedPackageIntent, setSelectedPackageIntent] = useState<SelectedPackage | null>(() =>
    parseSelectedPackage(searchParams.get('selected_package')),
  )
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const mountedRef = useRef(true)
  const selectionChangedByUserRef = useRef(false)
  const checkoutRunRef = useRef(0)
  const checkoutBusyRef = useRef(false)
  const pollCancelRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!user) return
    const balanceBucket = user.credits <= 0 ? 'zero' : user.credits <= 2 ? 'low' : user.credits <= 30 ? 'medium' : 'high'
    trackProductEvent(
      'credits_viewed',
      { balance_bucket: balanceBucket, placement: 'credits' },
      { once: `credits-viewed:${balanceBucket}`, page: 'credits' },
    )
    trackProductEvent(
      'pricing_viewed',
      { placement: 'credits', pricing_variant: 'control' },
      { once: 'pricing-viewed:credits', page: 'credits' },
    )
  }, [user])

  const cancelPollDelay = useCallback(() => {
    const cancel = pollCancelRef.current
    pollCancelRef.current = null
    cancel?.()
  }, [])

  const invalidateCheckoutRun = useCallback(() => {
    checkoutRunRef.current += 1
    checkoutBusyRef.current = false
    cancelPollDelay()
    if (mountedRef.current) setCheckoutLoading(false)
  }, [cancelPollDelay])

  const waitForCheckoutPoll = useCallback((delayMs: number, runId: number) => {
    cancelPollDelay()
    return new Promise<boolean>((resolve) => {
      let settled = false
      const finish = (active: boolean) => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        if (pollCancelRef.current === cancel) pollCancelRef.current = null
        resolve(active)
      }
      const timer = window.setTimeout(() => {
        finish(mountedRef.current && checkoutRunRef.current === runId)
      }, delayMs)
      const cancel = () => finish(false)
      pollCancelRef.current = cancel
    })
  }, [cancelPollDelay])

  const loadPackages = useCallback(async () => {
    setLoadingPackages(true)
    setPackagesError(null)
    try {
      const data = await fetchPackages()
      if (mountedRef.current) setPackages(data)
    } catch (err) {
      if (mountedRef.current) setPackagesError(err instanceof Error ? err.message : 'Erro ao carregar pacotes')
    } finally {
      if (mountedRef.current) setLoadingPackages(false)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    loadPackages()
    return () => {
      mountedRef.current = false
      checkoutRunRef.current += 1
      checkoutBusyRef.current = false
      cancelPollDelay()
    }
  }, [cancelPollDelay, loadPackages])

  // Handle return from MercadoPago / Stripe
  useEffect(() => {
    const status = searchParams.get('status')
    if (status === 'success') {
      // O webhook que credita e ASSINCRONO (~5-30s). Afirmar "creditos adicionados" aqui
      // contradizia a UI (saldo ainda antigo). Mensagem honesta + polling curto: o saldo
      // sobe sozinho quando o webhook processa.
      success('Pagamento aprovado', 'Seus créditos serão creditados em instantes.')
      void refreshUser()
      let tries = 0
      const poll = setInterval(() => {
        tries += 1
        void refreshUser()
        if (tries >= 10) clearInterval(poll)
      }, 3000)
      return () => clearInterval(poll)
    }
    if (status === 'failure') {
      error('Pagamento não aprovado', 'Tente novamente.')
    } else if (status === 'pending') {
      info('Pagamento pendente', 'Seus créditos serão adicionados assim que confirmado.')
      void refreshUser()
    }
  }, [error, info, refreshUser, searchParams, success])

  useEffect(() => {
    if (selectionChangedByUserRef.current) return
    const intent = parseSelectedPackage(searchParams.get('selected_package'))
    if (intent) {
      setSelectedPackageIntent(intent)
      return
    }
    const persistedIntent = parseSelectedPackage(user?.selected_package)
    if (persistedIntent) setSelectedPackageIntent(persistedIntent)
  }, [searchParams, user?.selected_package])

  const selectedPackage = packages.find(
    (pkg) => apiIdToSelectedPackage(pkg.id) === selectedPackageIntent,
  ) ?? null
  const selectedLabel = selectedPackageIntent ? selectedPackageLabel(selectedPackageIntent) : ''

  function releaseCheckout(runId: number) {
    if (!mountedRef.current || checkoutRunRef.current !== runId) return
    checkoutBusyRef.current = false
    setCheckoutLoading(false)
  }

  function finishSettledCheckout(
    outcome: CheckoutCreationResult | CheckoutStatus,
    attempt: StoredCheckoutAttempt,
    runId: number,
  ): boolean {
    if (!mountedRef.current || checkoutRunRef.current !== runId) return true
    if (outcome.state === 'pending') return false

    clearCheckoutAttempt(attempt)
    if (outcome.state === 'ready') {
      window.location.assign(outcome.checkout_url)
      return true
    }

    releaseCheckout(runId)
    error(
      outcome.state === 'cancelled' ? 'Checkout cancelado' : 'Checkout não concluído',
      'A tentativa anterior foi encerrada. Você já pode iniciar uma nova.',
    )
    return true
  }

  async function followPendingCheckout(
    initial: CheckoutCreationResult | CheckoutStatus,
    originalAttempt: StoredCheckoutAttempt,
    runId: number,
  ) {
    if (finishSettledCheckout(initial, originalAttempt, runId)) return

    const purchaseId = initial.purchase_id
    const attempt: StoredCheckoutAttempt = {
      ...originalAttempt,
      purchase_id: purchaseId,
    }
    writeCheckoutAttempt(attempt)

    for (const delayMs of CHECKOUT_POLL_DELAYS_MS) {
      const active = await waitForCheckoutPoll(delayMs, runId)
      if (!active) return

      const status = await fetchCheckoutStatus(purchaseId, provider)
      if (!mountedRef.current || checkoutRunRef.current !== runId) return
      if (finishSettledCheckout(status, attempt, runId)) return
    }

    if (!mountedRef.current || checkoutRunRef.current !== runId) return
    releaseCheckout(runId)
    info(
      'Checkout ainda em preparação',
      'Sua tentativa foi preservada. Clique novamente para consultar o mesmo checkout.',
    )
  }

  async function handleCheckout() {
    if (!selectedPackage || checkoutBusyRef.current) return
    cancelPollDelay()
    const runId = checkoutRunRef.current + 1
    checkoutRunRef.current = runId
    checkoutBusyRef.current = true
    setCheckoutLoading(true)
    let attempt: StoredCheckoutAttempt | null = null
    try {
      const fingerprint = `${provider}:${selectedPackage.id}`
      attempt = getOrCreateCheckoutAttempt(fingerprint)
      const initial = attempt.purchase_id
        ? await fetchCheckoutStatus(attempt.purchase_id, provider)
        : await createCheckout(selectedPackage.id, provider, attempt.idempotency_key)
      if (!mountedRef.current || checkoutRunRef.current !== runId) return
      await followPendingCheckout(initial, attempt, runId)
    } catch (err) {
      if (!mountedRef.current || checkoutRunRef.current !== runId) return
      if (err instanceof ApiError && err.status === 409) {
        if (attempt) clearCheckoutAttempt(attempt)
        error(
          'Tentativa de checkout expirada',
          'A chave anterior não pode mais ser usada. Tente novamente para criar uma nova.',
        )
        releaseCheckout(runId)
        return
      }
      error(
        'Falha ao iniciar checkout',
        err instanceof Error ? err.message : 'Tente novamente em instantes.',
      )
      releaseCheckout(runId)
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {packagesError ? (
        <InlineError
          title="Não foi possível carregar os pacotes"
          description={packagesError}
          onRetry={() => loadPackages()}
        />
      ) : (
        <>
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              Meus Créditos
            </h1>
            <div className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-full" style={{ background: 'var(--bg-surface)' }}>
              <span className="text-3xl font-bold" style={{ color: 'var(--accent-primary, #ff5638)' }}>
                {user?.credits ?? 0}
              </span>
              <span style={{ color: 'var(--text-secondary)' }}>créditos disponíveis</span>
            </div>
            {(() => {
              const bonusPercent = packages.find((p) => p.bonus_percent > 0)?.bonus_percent
              return bonusPercent ? (
                <p className="mt-3 text-sm font-medium" style={{ color: '#4ade80' }}>
                  🎉 Promoção beta: +{bonusPercent}% de créditos bônus em todos os pacotes
                </p>
              ) : null
            })()}
          </div>

          {/* Provider selector */}
          <div className="flex justify-center gap-2 mb-6">
            {([
              { id: 'mercadopago', label: 'Pix', sub: 'Pix e cartão' },
              { id: 'stripe', label: 'Cartão', sub: 'Stripe internacional' },
            ] as const).map((opt) => (
              <button
                key={opt.id}
                onClick={() => {
                  if (opt.id === provider) return
                  invalidateCheckoutRun()
                  setProvider(opt.id)
                }}
                aria-pressed={provider === opt.id}
                className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer"
                style={{
                  background: provider === opt.id ? 'var(--bg-raised)' : 'transparent',
                  border: provider === opt.id
                    ? '1px solid var(--accent-primary, #ff5638)'
                    : '1px solid var(--border-subtle)',
                  color: provider === opt.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                }}
              >
                {opt.label}
                <span className="block text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{opt.sub}</span>
              </button>
            ))}
          </div>

          {/* Packages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
            {loadingPackages ? (
              <div className="md:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card h-64 animate-pulse" />
                <div className="card h-64 animate-pulse" />
                <div className="card h-64 animate-pulse" />
              </div>
            ) : (
              packages.map((pkg) => {
                const packageIntent = apiIdToSelectedPackage(pkg.id)
                return (
                  <CreditPackageCard
                    key={pkg.id}
                    pkg={pkg}
                    highlight={packageIntent === 'popular'}
                    badge={packageIntent === 'popular' ? 'Mais Popular' : packageIntent === 'professional' ? 'Melhor custo' : undefined}
                    selected={packageIntent === selectedPackageIntent}
                    onSelect={() => {
                      if (!packageIntent) return
                      trackProductEvent(
                        'pricing_package_selected',
                        { package: packageIntent, placement: 'credits' },
                        { page: 'credits' },
                      )
                      invalidateCheckoutRun()
                      selectionChangedByUserRef.current = true
                      setSelectedPackageIntent(packageIntent)
                    }}
                  />
                )
              })
            )}
          </div>

          {selectedPackage && (
            <div
              className="mb-12 flex flex-col items-center justify-between gap-4 rounded-2xl p-5 sm:flex-row"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
            >
              <div>
                <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {selectedLabel} selecionado
                </p>
                <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Você ainda pode escolher outro pacote antes de abrir o checkout.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCheckout}
                disabled={checkoutLoading}
                className="w-full rounded-xl px-5 py-3 text-sm font-semibold text-white transition-opacity disabled:opacity-50 sm:w-auto"
                style={{ background: 'linear-gradient(135deg, #ff5638, #3e9bff)' }}
              >
                {checkoutLoading ? 'Abrindo checkout...' : `Continuar com ${selectedLabel}`}
              </button>
            </div>
          )}

          {/* History */}
          <div>
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Histórico de compras
            </h2>
            <PurchaseHistory />
          </div>
        </>
      )}
    </div>
  )
}
