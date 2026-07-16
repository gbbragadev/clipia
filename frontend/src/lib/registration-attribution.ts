export const ATTRIBUTION_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
  'utm_id',
] as const

const AUTH_SAFE_UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'] as const
const STORAGE_PREFIX = 'clipia_'

export type AttributionKey = (typeof ATTRIBUTION_KEYS)[number]
export type StoredAttribution = Partial<Record<AttributionKey, string>> & {
  referral_code?: string
  offer_code?: string
}
export type RegistrationAttribution = Partial<Record<(typeof AUTH_SAFE_UTM_KEYS)[number], string>> & {
  referral_code?: string
  offer_code?: string
}

export interface AttributionStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface AttributionSearchParams {
  get(key: string): string | null
}

export function captureRegistrationAttribution(
  searchParams: AttributionSearchParams,
  storage: AttributionStorage,
): void {
  for (const key of ATTRIBUTION_KEYS) {
    const value = searchParams.get(key)
    if (value) storage.setItem(`${STORAGE_PREFIX}${key}`, value)
  }
  const referral = searchParams.get('ref')
  if (referral) storage.setItem(`${STORAGE_PREFIX}ref`, referral)
  const offer = searchParams.get('offer')
  if (offer) storage.setItem(`${STORAGE_PREFIX}offer`, offer)
}

export function readStoredAttribution(storage: AttributionStorage): StoredAttribution {
  const result: StoredAttribution = {}
  for (const key of ATTRIBUTION_KEYS) {
    const value = storage.getItem(`${STORAGE_PREFIX}${key}`)
    if (value) result[key] = value
  }
  const referral = storage.getItem(`${STORAGE_PREFIX}ref`)
  if (referral) result.referral_code = referral
  const offer = storage.getItem(`${STORAGE_PREFIX}offer`)
  if (offer) result.offer_code = offer
  return result
}

export function readRegistrationAttribution(storage: AttributionStorage): RegistrationAttribution {
  const stored = readStoredAttribution(storage)
  const result: RegistrationAttribution = {}
  for (const key of AUTH_SAFE_UTM_KEYS) {
    if (stored[key]) result[key] = stored[key]
  }
  if (stored.referral_code) result.referral_code = stored.referral_code
  if (stored.offer_code) result.offer_code = stored.offer_code
  return result
}

export function clearRegistrationAttribution(storage: AttributionStorage): void {
  for (const key of ATTRIBUTION_KEYS) storage.removeItem(`${STORAGE_PREFIX}${key}`)
  storage.removeItem(`${STORAGE_PREFIX}ref`)
  storage.removeItem(`${STORAGE_PREFIX}offer`)
}
