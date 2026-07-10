const API_BASE = '/api/v1'

export interface PublicConfig {
  welcome_credit_bonus: number
  purchase_bonus_percent: number
}

/** Fallback = defaults do backend (app/config.py) para render offline/erro. */
const FALLBACK: PublicConfig = { welcome_credit_bonus: 2, purchase_bonus_percent: 0 }

let cached: PublicConfig | null = null
let inflight: Promise<PublicConfig> | null = null

/** Valores de oferta exibidos na UI — guardrail do DESIGN.md: número prometido
 * NUNCA é hardcodado; vem daqui (fonte: GET /api/v1/config, cacheado por sessão). */
export function fetchPublicConfig(): Promise<PublicConfig> {
  if (cached) return Promise.resolve(cached)
  if (inflight) return inflight
  inflight = fetch(`${API_BASE}/config`)
    .then((r) => (r.ok ? r.json() : FALLBACK))
    .then((data: PublicConfig) => {
      cached = { ...FALLBACK, ...data }
      return cached
    })
    .catch(() => FALLBACK)
    .finally(() => {
      inflight = null
    })
  return inflight
}
