const SESSION_STORAGE_KEY = 'clipia_public_share_session_id'

export interface QualifiedViewPayload {
  anonymous_session_id: string
  dwell_ms: number
  page_visible: true
}

export interface QualifiedViewClock {
  now(): number
  setTimeout(callback: () => void, delayMs: number): unknown
  clearTimeout(handle: unknown): void
}

export interface QualifiedViewSchedulerOptions {
  token: string
  anonymousSessionId: string
  clock: QualifiedViewClock
  transport(token: string, payload: QualifiedViewPayload): Promise<unknown>
  retryDelaysMs?: readonly number[]
  shouldRetry?(error: unknown): boolean
  dwellMs?: number
}

export interface QualifiedViewSchedulerState {
  sent: boolean
  token: string
  attempts: number
}

interface SessionStorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

export function getDurableAnonymousSessionId(
  storage: SessionStorageLike,
  randomUUID: () => string,
): string {
  const stored = storage.getItem(SESSION_STORAGE_KEY)
  if (stored) return stored
  const created = randomUUID()
  storage.setItem(SESSION_STORAGE_KEY, created)
  return created
}

export function isTransientQualifiedViewError(error: unknown): boolean {
  const status = error && typeof error === 'object' && 'status' in error
    ? Number((error as { status?: unknown }).status)
    : Number.NaN
  return !Number.isFinite(status) || status === 408 || status === 429 || status >= 500
}

export class QualifiedViewScheduler {
  private token: string
  private readonly anonymousSessionId: string
  private readonly clock: QualifiedViewClock
  private readonly transport: QualifiedViewSchedulerOptions['transport']
  private readonly retryDelaysMs: readonly number[]
  private readonly shouldRetry: NonNullable<QualifiedViewSchedulerOptions['shouldRetry']>
  private readonly dwellMs: number
  private visible = false
  private visibleSince: number | null = null
  private visibleDwellMs = 0
  private timer: unknown = null
  private retryPending = false
  private retryIndex = 0
  private attempts = 0
  private sending = false
  private sent = false
  private terminalFailure = false
  private disposed = false
  private generation = 0

  constructor(options: QualifiedViewSchedulerOptions) {
    this.token = options.token
    this.anonymousSessionId = options.anonymousSessionId
    this.clock = options.clock
    this.transport = options.transport
    this.retryDelaysMs = options.retryDelaysMs ?? [500, 1500, 3000]
    this.shouldRetry = options.shouldRetry ?? isTransientQualifiedViewError
    this.dwellMs = options.dwellMs ?? 5000
  }

  setVisible(visible: boolean): void {
    if (this.disposed || this.visible === visible) return
    this.visible = visible
    if (!visible) {
      this.accrueVisibleDwell()
      this.clearTimer()
      return
    }
    this.scheduleCurrentState()
  }

  setToken(token: string): void {
    if (this.disposed || token === this.token) return
    this.generation += 1
    this.clearTimer()
    this.token = token
    this.visibleSince = null
    this.visibleDwellMs = 0
    this.retryPending = false
    this.retryIndex = 0
    this.attempts = 0
    this.sending = false
    this.sent = false
    this.terminalFailure = false
    if (this.visible) this.scheduleCurrentState()
  }

  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    this.generation += 1
    this.accrueVisibleDwell()
    this.clearTimer()
  }

  getState(): QualifiedViewSchedulerState {
    return { sent: this.sent, token: this.token, attempts: this.attempts }
  }

  private scheduleCurrentState(): void {
    if (this.disposed || !this.visible || this.sent || this.sending || this.terminalFailure || this.timer !== null) return
    if (this.retryPending) {
      const delay = this.retryDelaysMs[this.retryIndex]
      if (delay === undefined) {
        this.retryPending = false
        this.terminalFailure = true
        return
      }
      this.timer = this.clock.setTimeout(() => {
        this.timer = null
        if (this.disposed || !this.visible) return
        this.retryPending = false
        this.retryIndex += 1
        this.send()
      }, delay)
      return
    }

    if (this.visibleSince === null) this.visibleSince = this.clock.now()
    const remaining = Math.max(0, this.dwellMs - this.visibleDwellMs)
    this.timer = this.clock.setTimeout(() => {
      this.timer = null
      this.accrueVisibleDwell()
      if (this.visible) this.send()
    }, remaining)
  }

  private accrueVisibleDwell(): void {
    if (this.visibleSince === null) return
    this.visibleDwellMs += Math.max(0, this.clock.now() - this.visibleSince)
    this.visibleSince = null
  }

  private clearTimer(): void {
    if (this.timer === null) return
    this.clock.clearTimeout(this.timer)
    this.timer = null
  }

  private send(): void {
    if (this.disposed || !this.visible || this.sent || this.sending || this.terminalFailure) return
    this.accrueVisibleDwell()
    if (this.visibleDwellMs < this.dwellMs) {
      this.scheduleCurrentState()
      return
    }

    const generation = this.generation
    const token = this.token
    this.sending = true
    this.attempts += 1
    const payload: QualifiedViewPayload = {
      anonymous_session_id: this.anonymousSessionId,
      dwell_ms: Math.max(this.dwellMs, Math.round(this.visibleDwellMs)),
      page_visible: true,
    }

    let request: Promise<unknown>
    try {
      request = this.transport(token, payload)
    } catch (error) {
      request = Promise.reject(error)
    }
    void request.then(
      () => {
        if (this.disposed || generation !== this.generation) return
        this.sending = false
        this.sent = true
        this.clearTimer()
      },
      (error: unknown) => {
        if (this.disposed || generation !== this.generation) return
        this.sending = false
        if (!this.shouldRetry(error) || this.retryIndex >= this.retryDelaysMs.length) {
          this.terminalFailure = true
          this.retryPending = false
          return
        }
        this.retryPending = true
        this.scheduleCurrentState()
      },
    )
  }
}
