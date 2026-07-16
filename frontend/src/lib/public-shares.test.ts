import assert from 'node:assert/strict'
import test from 'node:test'

async function loadPublicShareActions(): Promise<Record<string, unknown>> {
  return import('./public-share-actions.ts').catch(() => ({})) as Promise<Record<string, unknown>>
}

test('publish and revoke use encoded job routes with their exact HTTP methods', async () => {
  const module = await loadPublicShareActions()
  assert.equal(typeof module.publishPublicShare, 'function')
  assert.equal(typeof module.revokePublicShare, 'function')
  const publishPublicShare = module.publishPublicShare as (jobId: string, transport: (request: Record<string, unknown>) => Promise<unknown>) => Promise<unknown>
  const revokePublicShare = module.revokePublicShare as (jobId: string, transport: (request: Record<string, unknown>) => Promise<unknown>) => Promise<void>
  const requests: Array<Record<string, unknown>> = []
  const transport = async (request: Record<string, unknown>) => {
    requests.push(request)
    return request.method === 'POST'
      ? { token: 'token', url: 'https://clipia.com.br/v/token', title: 'Topic', active: true }
      : undefined
  }

  await publishPublicShare('job/../secret', transport)
  await revokePublicShare('job/../secret', transport)

  assert.deepEqual(requests, [
    { path: '/videos/job%2F..%2Fsecret/public-share', method: 'POST' },
    { path: '/videos/job%2F..%2Fsecret/public-share', method: 'DELETE' },
  ])
})

test('public sharing gating accepts delivered editable or completed videos with a downloadable artifact', async () => {
  const module = await loadPublicShareActions()
  assert.equal(typeof module.canManagePublicShare, 'function')
  const canManagePublicShare = module.canManagePublicShare as (job: { status: string; download_url: string | null }) => boolean

  assert.equal(canManagePublicShare({ status: 'completed', download_url: '/download/video' }), true)
  assert.equal(canManagePublicShare({ status: 'completed', download_url: null }), false)
  assert.equal(canManagePublicShare({ status: 'editable', download_url: '/download/video' }), true)
  assert.equal(canManagePublicShare({ status: 'processing', download_url: '/download/video' }), false)
})
