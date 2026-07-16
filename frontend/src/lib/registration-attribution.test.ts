import assert from 'node:assert/strict'
import test from 'node:test'

class MemoryStorage {
  values = new Map<string, string>()
  getItem(key: string): string | null { return this.values.get(key) ?? null }
  setItem(key: string, value: string): void { this.values.set(key, value) }
  removeItem(key: string): void { this.values.delete(key) }
}

async function loadAttribution(): Promise<Record<string, unknown>> {
  return import('./registration-attribution.ts').catch(() => ({})) as Promise<Record<string, unknown>>
}

test('campaign query is captured separately and registration reads only allowed attribution fields', async () => {
  const module = await loadAttribution()
  assert.equal(typeof module.captureRegistrationAttribution, 'function')
  assert.equal(typeof module.readRegistrationAttribution, 'function')
  const capture = module.captureRegistrationAttribution as (params: URLSearchParams, storage: MemoryStorage) => void
  const read = module.readRegistrationAttribution as (storage: MemoryStorage) => Record<string, string>
  const storage = new MemoryStorage()
  const params = new URLSearchParams({
    offer: 'creator20_v1',
    ref: 'invite123',
    utm_source: 'meta',
    utm_medium: 'paid_social',
    utm_campaign: 'clipia_creator20_pilot',
    utm_content: 'creative-a',
    utm_term: 'ignored-by-auth',
  })

  capture(params, storage)

  assert.equal(storage.getItem('clipia_offer'), 'creator20_v1')
  assert.equal(storage.getItem('clipia_utm_source'), 'meta')
  assert.deepEqual(read(storage), {
    utm_source: 'meta',
    utm_medium: 'paid_social',
    utm_campaign: 'clipia_creator20_pilot',
    referral_code: 'invite123',
    offer_code: 'creator20_v1',
  })
})

test('clearing attribution removes offer, referral and every UTM only after the caller requests it', async () => {
  const module = await loadAttribution()
  assert.equal(typeof module.captureRegistrationAttribution, 'function')
  assert.equal(typeof module.clearRegistrationAttribution, 'function')
  const capture = module.captureRegistrationAttribution as (params: URLSearchParams, storage: MemoryStorage) => void
  const clear = module.clearRegistrationAttribution as (storage: MemoryStorage) => void
  const storage = new MemoryStorage()
  capture(new URLSearchParams({
    offer: 'creator20_v1',
    ref: 'invite123',
    utm_source: 'meta',
    utm_medium: 'paid_social',
    utm_campaign: 'pilot',
    utm_content: 'creative',
    utm_term: 'term',
    utm_id: 'id',
  }), storage)

  assert.equal(storage.values.size > 0, true)
  clear(storage)
  assert.equal(storage.values.size, 0)
})
