import assert from 'node:assert/strict'
import test from 'node:test'

interface TimerTask {
  at: number
  callback: () => void
}

class FakeClock {
  time = 0
  nextId = 1
  tasks = new Map<number, TimerTask>()

  now = () => this.time

  setTimeout = (callback: () => void, delayMs: number): number => {
    const id = this.nextId++
    this.tasks.set(id, { at: this.time + Math.max(0, delayMs), callback })
    return id
  }

  clearTimeout = (id: unknown): void => {
    this.tasks.delete(id as number)
  }

  pendingCount(): number {
    return this.tasks.size
  }

  async advance(delayMs: number): Promise<void> {
    const target = this.time + delayMs
    while (true) {
      const due = [...this.tasks.entries()]
        .filter(([, task]) => task.at <= target)
        .sort((left, right) => left[1].at - right[1].at)[0]
      if (!due) break
      const [id, task] = due
      this.tasks.delete(id)
      this.time = task.at
      task.callback()
      await Promise.resolve()
      await Promise.resolve()
    }
    this.time = target
    await Promise.resolve()
    await Promise.resolve()
  }
}

async function loadScheduler(): Promise<new (options: Record<string, unknown>) => {
  setVisible: (visible: boolean) => void
  setToken: (token: string) => void
  dispose: () => void
  getState: () => { sent: boolean; token: string; attempts: number }
}> {
  const module = await import('./qualified-view-scheduler.ts').catch(() => ({})) as Record<string, unknown>
  assert.equal(typeof module.QualifiedViewScheduler, 'function')
  return module.QualifiedViewScheduler as new (options: Record<string, unknown>) => {
    setVisible: (visible: boolean) => void
    setToken: (token: string) => void
    dispose: () => void
    getState: () => { sent: boolean; token: string; attempts: number }
  }
}

test('anonymous session id is durable in storage', async () => {
  const module = await import('./qualified-view-scheduler.ts').catch(() => ({})) as Record<string, unknown>
  assert.equal(typeof module.getDurableAnonymousSessionId, 'function')
  const getDurableAnonymousSessionId = module.getDurableAnonymousSessionId as (
    storage: { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void },
    randomUUID: () => string,
  ) => string
  const values = new Map<string, string>()
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
  }

  const first = getDurableAnonymousSessionId(storage, () => '66666666-6666-4666-8666-666666666666')
  const second = getDurableAnonymousSessionId(storage, () => '77777777-7777-4777-8777-777777777777')

  assert.equal(first, '66666666-6666-4666-8666-666666666666')
  assert.equal(second, first)
})

test('anonymous session id stays lazy until qualified send and is reused by retries', async () => {
  const module = await import('./qualified-view-scheduler.ts') as Record<string, unknown>
  const getDurableAnonymousSessionId = module.getDurableAnonymousSessionId as (
    storage: { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void },
    randomUUID: () => string,
  ) => string
  const Scheduler = await loadScheduler()
  const clock = new FakeClock()
  const values = new Map<string, string>()
  let reads = 0
  let writes = 0
  let creations = 0
  const storage = {
    getItem: (key: string) => {
      reads += 1
      return values.get(key) ?? null
    },
    setItem: (key: string, value: string) => {
      writes += 1
      values.set(key, value)
    },
  }
  const getAnonymousSessionId = () => getDurableAnonymousSessionId(storage, () => {
    creations += 1
    return '88888888-8888-4888-8888-888888888888'
  })
  const payloads: Array<Record<string, unknown>> = []
  let attempts = 0
  const scheduler = new Scheduler({
    token: 'token-lazy',
    getAnonymousSessionId,
    clock,
    transport: async (_token: string, payload: Record<string, unknown>) => {
      attempts += 1
      payloads.push(payload)
      if (attempts === 1) throw new Error('temporary')
    },
    retryDelaysMs: [100],
    shouldRetry: () => true,
  })

  await clock.advance(20_000)
  assert.deepEqual({ reads, writes, creations, attempts }, { reads: 0, writes: 0, creations: 0, attempts: 0 })
  scheduler.setVisible(true)
  await clock.advance(4999)
  assert.deepEqual({ reads, writes, creations, attempts }, { reads: 0, writes: 0, creations: 0, attempts: 0 })
  scheduler.setVisible(false)
  await clock.advance(20_000)
  assert.deepEqual({ reads, writes, creations, attempts }, { reads: 0, writes: 0, creations: 0, attempts: 0 })

  scheduler.setVisible(true)
  await clock.advance(1)
  assert.deepEqual({ reads, writes, creations, attempts }, { reads: 1, writes: 1, creations: 1, attempts: 1 })
  assert.equal(payloads[0]?.anonymous_session_id, '88888888-8888-4888-8888-888888888888')
  await clock.advance(100)
  assert.deepEqual({ reads, writes, creations, attempts }, { reads: 1, writes: 1, creations: 1, attempts: 2 })
  assert.equal(payloads[1]?.anonymous_session_id, payloads[0]?.anonymous_session_id)

  let disposedReads = 0
  let disposedWrites = 0
  let disposedCreations = 0
  const disposed = new Scheduler({
    token: 'token-disposed',
    getAnonymousSessionId: () => getDurableAnonymousSessionId({
      getItem: () => { disposedReads += 1; return null },
      setItem: () => { disposedWrites += 1 },
    }, () => { disposedCreations += 1; return '99999999-9999-4999-8999-999999999999' }),
    clock,
    transport: async () => undefined,
  })
  disposed.setVisible(true)
  await clock.advance(4999)
  disposed.dispose()
  await clock.advance(10_000)
  assert.deepEqual(
    { disposedReads, disposedWrites, disposedCreations },
    { disposedReads: 0, disposedWrites: 0, disposedCreations: 0 },
  )
})

test('qualified dwell accumulates only while visible and sends the exact payload once', async () => {
  const Scheduler = await loadScheduler()
  const clock = new FakeClock()
  const calls: Array<{ token: string; payload: Record<string, unknown> }> = []
  const scheduler = new Scheduler({
    token: 'token-a',
    getAnonymousSessionId: () => '11111111-1111-4111-8111-111111111111',
    clock,
    transport: async (token: string, payload: Record<string, unknown>) => { calls.push({ token, payload }) },
    retryDelaysMs: [100, 200],
    shouldRetry: () => true,
  })

  scheduler.setVisible(true)
  await clock.advance(3000)
  scheduler.setVisible(false)
  await clock.advance(20_000)
  assert.equal(calls.length, 0)
  assert.equal(clock.pendingCount(), 0)

  scheduler.setVisible(true)
  await clock.advance(1999)
  assert.equal(calls.length, 0)
  await clock.advance(1)

  assert.deepEqual(calls, [{
    token: 'token-a',
    payload: {
      anonymous_session_id: '11111111-1111-4111-8111-111111111111',
      dwell_ms: 5000,
      page_visible: true,
    },
  }])
  assert.equal(scheduler.getState().sent, true)
  assert.equal(clock.pendingCount(), 0)
})

test('transient failures retry with bounded backoff and mark sent only after success', async () => {
  const Scheduler = await loadScheduler()
  const clock = new FakeClock()
  let calls = 0
  const scheduler = new Scheduler({
    token: 'token-retry',
    getAnonymousSessionId: () => '22222222-2222-4222-8222-222222222222',
    clock,
    transport: async () => {
      calls += 1
      if (calls < 3) throw new Error('temporary')
    },
    retryDelaysMs: [100, 200],
    shouldRetry: () => true,
  })

  scheduler.setVisible(true)
  await clock.advance(5000)
  assert.equal(calls, 1)
  assert.equal(scheduler.getState().sent, false)
  await clock.advance(99)
  assert.equal(calls, 1)
  await clock.advance(1)
  assert.equal(calls, 2)
  assert.equal(scheduler.getState().sent, false)
  await clock.advance(200)
  assert.equal(calls, 3)
  assert.equal(scheduler.getState().sent, true)
  await clock.advance(10_000)
  assert.equal(calls, 3)
  assert.equal(clock.pendingCount(), 0)
})

test('retry pauses while hidden and permanent or exhausted failures never loop', async () => {
  const Scheduler = await loadScheduler()
  const clock = new FakeClock()
  let transientCalls = 0
  const transient = new Scheduler({
    token: 'token-hidden',
    getAnonymousSessionId: () => '33333333-3333-4333-8333-333333333333',
    clock,
    transport: async () => { transientCalls += 1; throw new Error('temporary') },
    retryDelaysMs: [100, 200],
    shouldRetry: () => true,
  })
  transient.setVisible(true)
  await clock.advance(5000)
  transient.setVisible(false)
  assert.equal(clock.pendingCount(), 0)
  await clock.advance(5000)
  assert.equal(transientCalls, 1)
  transient.setVisible(true)
  await clock.advance(100)
  await clock.advance(200)
  assert.equal(transientCalls, 3)
  assert.equal(transient.getState().sent, false)
  assert.equal(clock.pendingCount(), 0)

  let permanentCalls = 0
  const permanent = new Scheduler({
    token: 'token-permanent',
    getAnonymousSessionId: () => '44444444-4444-4444-8444-444444444444',
    clock,
    transport: async () => { permanentCalls += 1; throw new Error('bad request') },
    retryDelaysMs: [100, 200],
    shouldRetry: () => false,
  })
  permanent.setVisible(true)
  await clock.advance(5000)
  await clock.advance(10_000)
  assert.equal(permanentCalls, 1)
  assert.equal(permanent.getState().sent, false)
  assert.equal(clock.pendingCount(), 0)
})

test('changing token resets dwell and ignores an old in-flight success', async () => {
  const Scheduler = await loadScheduler()
  const clock = new FakeClock()
  let sessionIdCalls = 0
  const pending: Array<{ token: string; payload: Record<string, unknown>; resolve: () => void }> = []
  const scheduler = new Scheduler({
    token: 'token-old',
    getAnonymousSessionId: () => {
      sessionIdCalls += 1
      return '55555555-5555-4555-8555-555555555555'
    },
    clock,
    transport: (token: string, payload: Record<string, unknown>) => new Promise<void>((resolve) => {
      pending.push({ token, payload, resolve })
    }),
    retryDelaysMs: [100],
    shouldRetry: () => true,
  })

  scheduler.setVisible(true)
  await clock.advance(5000)
  assert.equal(pending[0]?.token, 'token-old')
  scheduler.setToken('token-new')
  pending[0].resolve()
  await Promise.resolve()
  await Promise.resolve()
  assert.deepEqual(scheduler.getState(), { sent: false, token: 'token-new', attempts: 0 })

  await clock.advance(4999)
  assert.equal(pending.length, 1)
  await clock.advance(1)
  assert.equal(pending[1]?.token, 'token-new')
  assert.equal(sessionIdCalls, 1)
  assert.equal(pending[1]?.payload.anonymous_session_id, pending[0]?.payload.anonymous_session_id)
  pending[1].resolve()
  await Promise.resolve()
  await Promise.resolve()
  assert.equal(scheduler.getState().sent, true)

  scheduler.dispose()
  assert.equal(clock.pendingCount(), 0)
})
