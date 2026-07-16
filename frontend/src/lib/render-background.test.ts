import assert from 'node:assert/strict'
import test from 'node:test'

test('background render becomes a persistent ready notice when the API completes', async () => {
  const module = await import('./render-background.ts').catch(() => null)
  assert.ok(module, 'render-background module should exist')

  const notices = [{
    jobId: 'job-editor',
    revision: 2,
    topic: 'Cérebro',
    startedAt: '2026-07-15T12:00:00.000Z',
    status: 'rendering' as const,
    completedAt: null,
  }]
  const reconciled = module.reconcileBackgroundRenders(notices, [{
    job_id: 'job-editor',
    status: 'completed',
  }], '2026-07-15T12:12:00.000Z')

  assert.equal(reconciled[0].status, 'ready')
  assert.equal(reconciled[0].completedAt, '2026-07-15T12:12:00.000Z')
})

test('invalid and duplicate stored notices are discarded deterministically', async () => {
  const module = await import('./render-background.ts').catch(() => null)
  assert.ok(module, 'render-background module should exist')

  const parsed = module.parseBackgroundRenders(JSON.stringify([
    { jobId: 'job-1', revision: 1, topic: 'A', startedAt: '2026-07-15T12:00:00.000Z', status: 'rendering' },
    { jobId: 'job-1', revision: 2, topic: 'A', startedAt: '2026-07-15T12:01:00.000Z', status: 'rendering' },
    { jobId: '../unsafe', revision: -1, topic: 12, startedAt: 'not-a-date', status: 'ready' },
  ]))

  assert.deepEqual(parsed.map((notice) => [notice.jobId, notice.revision]), [['job-1', 2]])
})
