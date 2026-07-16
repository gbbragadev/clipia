export const BACKGROUND_RENDER_STORAGE_KEY = 'clipia_background_renders_v1'

export interface BackgroundRenderNotice {
  jobId: string
  revision: number
  topic: string
  startedAt: string
  status: 'rendering' | 'ready' | 'error'
  completedAt: string | null
}

interface JobRenderStatus {
  job_id: string
  status: string
}

function isValidIso(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function normalizeNotice(value: unknown): BackgroundRenderNotice | null {
  if (!value || typeof value !== 'object') return null
  const notice = value as Partial<BackgroundRenderNotice>
  if (
    typeof notice.jobId !== 'string'
    || !/^[A-Za-z0-9-]{1,64}$/.test(notice.jobId)
    || !Number.isSafeInteger(notice.revision)
    || Number(notice.revision) < 0
    || typeof notice.topic !== 'string'
    || !isValidIso(notice.startedAt)
    || !['rendering', 'ready', 'error'].includes(notice.status ?? '')
  ) {
    return null
  }
  return {
    jobId: notice.jobId,
    revision: Number(notice.revision),
    topic: notice.topic.slice(0, 200),
    startedAt: notice.startedAt,
    status: notice.status as BackgroundRenderNotice['status'],
    completedAt: isValidIso(notice.completedAt) ? notice.completedAt : null,
  }
}

export function parseBackgroundRenders(raw: string | null): BackgroundRenderNotice[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    const byJob = new Map<string, BackgroundRenderNotice>()
    for (const candidate of parsed) {
      const notice = normalizeNotice(candidate)
      if (!notice) continue
      const previous = byJob.get(notice.jobId)
      if (
        !previous
        || notice.revision > previous.revision
        || (notice.revision === previous.revision && notice.startedAt > previous.startedAt)
      ) {
        byJob.set(notice.jobId, notice)
      }
    }
    return [...byJob.values()].slice(-10)
  } catch {
    return []
  }
}

export function reconcileBackgroundRenders(
  notices: BackgroundRenderNotice[],
  jobs: JobRenderStatus[],
  nowIso = new Date().toISOString(),
): BackgroundRenderNotice[] {
  const statuses = new Map(jobs.map((job) => [job.job_id, job.status]))
  return notices.map((notice) => {
    if (notice.status !== 'rendering') return notice
    const status = statuses.get(notice.jobId)
    if (status === 'completed' || status === 'editable') {
      return { ...notice, status: 'ready', completedAt: nowIso }
    }
    if (status === 'error' || status === 'failed') {
      return { ...notice, status: 'error', completedAt: nowIso }
    }
    return notice
  })
}

export function readBackgroundRenders(storage: Pick<Storage, 'getItem'> = window.localStorage): BackgroundRenderNotice[] {
  return parseBackgroundRenders(storage.getItem(BACKGROUND_RENDER_STORAGE_KEY))
}

export function writeBackgroundRenders(
  notices: BackgroundRenderNotice[],
  storage: Pick<Storage, 'setItem'> = window.localStorage,
): void {
  storage.setItem(BACKGROUND_RENDER_STORAGE_KEY, JSON.stringify(notices.slice(-10)))
}

export function trackBackgroundRender(
  notice: Omit<BackgroundRenderNotice, 'status' | 'completedAt'>,
  storage: Pick<Storage, 'getItem' | 'setItem'> = window.localStorage,
): BackgroundRenderNotice[] {
  const next: BackgroundRenderNotice = { ...notice, status: 'rendering', completedAt: null }
  const notices = readBackgroundRenders(storage)
    .filter((existing) => existing.jobId !== notice.jobId)
    .concat(next)
    .slice(-10)
  writeBackgroundRenders(notices, storage)
  return notices
}

export function dismissBackgroundRender(
  jobId: string,
  storage: Pick<Storage, 'getItem' | 'setItem'> = window.localStorage,
): BackgroundRenderNotice[] {
  const notices = readBackgroundRenders(storage).filter((notice) => notice.jobId !== jobId)
  writeBackgroundRenders(notices, storage)
  return notices
}
