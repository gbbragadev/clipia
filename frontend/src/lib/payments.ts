import { getToken } from '@/lib/auth'
import { fetchJson } from '@/lib/http'

const API_BASE = ''
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export interface CreditPackage {
  id: string
  name: string
  credits: number
  price_brl: number
  price_display: string
  bonus_percent: number
  bonus_credits: number
}

export interface PurchaseHistoryItem {
  id: string
  package_name: string
  credits_amount: number
  price_brl: number
  status: string
  created_at: string
  paid_at: string | null
}

export type PaymentProvider = 'mercadopago' | 'stripe'
export type CheckoutDispatchState = 'pending' | 'ready' | 'failed' | 'cancelled'

export interface ReadyCheckout {
  state: 'ready'
  purchase_id: string
  checkout_url: string
}

export interface PendingCheckout {
  state: 'pending'
  purchase_id: string
  dispatch_id: string
}

export type CheckoutCreationResult = ReadyCheckout | PendingCheckout

export type CheckoutStatus =
  | (ReadyCheckout & { dispatch_id: string })
  | PendingCheckout
  | {
      state: 'failed' | 'cancelled'
      purchase_id: string
      dispatch_id: string
    }

function authHeaders(): Record<string, string> {
  const token = getToken()
  if (!token) throw new Error('Não autenticado')
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readUuid(value: unknown, field: string): string {
  if (typeof value !== 'string' || !UUID_PATTERN.test(value)) {
    throw new Error(`Resposta de checkout inválida: ${field}`)
  }
  return value.toLowerCase()
}

function assertIdempotencyKey(value: string): void {
  if (!/^[\x21-\x7e]{1,200}$/.test(value)) {
    throw new Error('Chave idempotente inválida')
  }
}

const CHECKOUT_HOSTS: Record<PaymentProvider, ReadonlySet<string>> = {
  mercadopago: new Set([
    'www.mercadopago.com',
    'sandbox.mercadopago.com',
    'www.mercadopago.com.br',
    'sandbox.mercadopago.com.br',
  ]),
  stripe: new Set(['checkout.stripe.com']),
}

function readCheckoutUrl(value: unknown, provider: PaymentProvider): string {
  if (typeof value !== 'string' || !value || value !== value.trim()) {
    throw new Error('Resposta de checkout inválida: checkout_url')
  }

  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error('Resposta de checkout inválida: checkout_url')
  }

  if (parsed.username || parsed.password) {
    throw new Error('Resposta de checkout inválida: checkout_url')
  }

  const hostname = parsed.hostname.toLowerCase()
  const currentLocation = typeof window !== 'undefined' ? window.location : null
  const sameOrigin = currentLocation !== null && parsed.origin === currentLocation.origin
  const currentHostname = currentLocation?.hostname.toLowerCase() ?? ''
  const currentOriginIsLocalQa =
    currentLocation?.protocol === 'http:' &&
    (currentHostname === 'localhost' || currentHostname === '127.0.0.1' || currentHostname === '[::1]')
  const secureProviderUrl =
    parsed.protocol === 'https:' &&
    ((CHECKOUT_HOSTS[provider].has(hostname) && parsed.port === '') || sameOrigin)
  const localQaUrl = parsed.protocol === 'http:' && sameOrigin && currentOriginIsLocalQa

  if (!secureProviderUrl && !localQaUrl) {
    throw new Error('Resposta de checkout inválida: checkout_url')
  }
  return parsed.toString()
}

function normalizeCheckoutCreation(
  payload: unknown,
  provider: PaymentProvider,
): CheckoutCreationResult {
  if (!isRecord(payload)) throw new Error('Resposta de checkout inválida')

  const purchaseId = readUuid(payload.purchase_id, 'purchase_id')
  if (payload.state === 'pending') {
    return {
      state: 'pending',
      purchase_id: purchaseId,
      dispatch_id: readUuid(payload.dispatch_id, 'dispatch_id'),
    }
  }
  if (payload.state !== undefined && payload.state !== 'ready') {
    throw new Error('Resposta de checkout inválida: state')
  }
  return {
    state: 'ready',
    purchase_id: purchaseId,
    checkout_url: readCheckoutUrl(payload.checkout_url, provider),
  }
}

function normalizeCheckoutStatus(
  payload: unknown,
  expectedPurchaseId: string,
  provider: PaymentProvider,
): CheckoutStatus {
  if (!isRecord(payload)) throw new Error('Resposta de checkout inválida')

  const purchaseId = readUuid(payload.purchase_id, 'purchase_id')
  if (purchaseId !== expectedPurchaseId) {
    throw new Error('Resposta de checkout inválida: purchase_id divergente')
  }
  const dispatchId = readUuid(payload.dispatch_id, 'dispatch_id')
  if (
    payload.state !== 'pending' &&
    payload.state !== 'ready' &&
    payload.state !== 'failed' &&
    payload.state !== 'cancelled'
  ) {
    throw new Error('Resposta de checkout inválida: state')
  }

  if (payload.state === 'ready') {
    return {
      state: 'ready',
      purchase_id: purchaseId,
      dispatch_id: dispatchId,
      checkout_url: readCheckoutUrl(payload.checkout_url, provider),
    }
  }
  return {
    state: payload.state,
    purchase_id: purchaseId,
    dispatch_id: dispatchId,
  }
}

export async function fetchPackages(): Promise<CreditPackage[]> {
  return fetchJson(
    `${API_BASE}/api/v1/credits/packages`,
    { headers: authHeaders() },
    'Erro ao carregar pacotes',
  )
}

export async function createCheckout(
  packageId: string,
  provider: PaymentProvider,
  idempotencyKey: string,
): Promise<CheckoutCreationResult> {
  assertIdempotencyKey(idempotencyKey)
  const data = await fetchJson<unknown>(
    `${API_BASE}/api/v1/credits/checkout`,
    {
      method: 'POST',
      headers: { ...authHeaders(), 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ package: packageId, provider }),
    },
    'Erro ao criar checkout',
  )
  return normalizeCheckoutCreation(data, provider)
}

export async function fetchCheckoutStatus(
  purchaseId: string,
  provider: PaymentProvider,
): Promise<CheckoutStatus> {
  const normalizedPurchaseId = readUuid(purchaseId, 'purchase_id')
  const data = await fetchJson<unknown>(
    `${API_BASE}/api/v1/credits/checkout/${encodeURIComponent(normalizedPurchaseId)}`,
    { headers: authHeaders() },
    'Erro ao consultar checkout',
  )
  return normalizeCheckoutStatus(data, normalizedPurchaseId, provider)
}

export async function fetchHistory(): Promise<PurchaseHistoryItem[]> {
  const data = await fetchJson<{ purchases: PurchaseHistoryItem[] }>(
    `${API_BASE}/api/v1/credits/history`,
    { headers: authHeaders() },
    'Erro ao carregar historico',
  )
  return data.purchases
}
