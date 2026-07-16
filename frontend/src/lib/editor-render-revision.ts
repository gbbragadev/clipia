import type {
  CompositionData,
  RenderRevisionEntry,
  RevisionSnapshot,
} from '../remotion/types.ts'

export interface RenderRevisionState {
  editRevision: number
  renderedRevision: number
  renderingRevision: number | null
  renderedAt: string | null
}

const MAX_RENDER_HISTORY = 5

const MUSIC_LABELS: Record<string, string> = {
  'lofi-chill': 'Lo-Fi Chill',
  'upbeat-energy': 'Upbeat Energy',
  'dramatic-epic': 'Dramatic Epic',
  'ambient-calm': 'Ambient Calm',
  'cinematic-tension': 'Cinematic Tension',
  'happy-pop': 'Happy Pop',
  'dark-ambient': 'Dark Ambient',
  inspirational: 'Inspirational',
  'dreamy-space': 'Dreamy Space',
  'tech-pulse': 'Tech Pulse',
}

function cloneSnapshot(snapshot: RevisionSnapshot): RevisionSnapshot {
  return {
    scenes: snapshot.scenes.map((scene) => ({
      ...scene,
      keywords_en: [...scene.keywords_en],
    })),
    sceneOrder: [...snapshot.sceneOrder],
    subtitleStyle: { ...snapshot.subtitleStyle },
    voiceConfig: { ...snapshot.voiceConfig },
    musicAssetId: snapshot.musicAssetId,
    musicVolume: snapshot.musicVolume,
    overlays: snapshot.overlays.map((overlay) => ({
      ...overlay,
      config: { ...overlay.config },
    })),
  }
}

function isSnapshot(value: unknown): value is RevisionSnapshot {
  if (!value || typeof value !== 'object') return false
  const snapshot = value as Partial<RevisionSnapshot>
  return Array.isArray(snapshot.scenes)
    && Array.isArray(snapshot.sceneOrder)
    && Boolean(snapshot.subtitleStyle && typeof snapshot.subtitleStyle === 'object')
    && Boolean(snapshot.voiceConfig && typeof snapshot.voiceConfig === 'object')
    && typeof snapshot.musicVolume === 'number'
    && Number.isFinite(snapshot.musicVolume)
    && Array.isArray(snapshot.overlays)
}

function normalizeIso(value: unknown): string | null {
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) ? value : null
}

function titleCase(value: string): string {
  return value.length > 0 ? `${value[0].toUpperCase()}${value.slice(1)}` : value
}

function sameValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

export function snapshotRevision(state: Pick<
  CompositionData,
  'scenes' | 'sceneOrder' | 'subtitleStyle' | 'voiceConfig' | 'musicAssetId' | 'musicVolume' | 'overlays'
>): RevisionSnapshot {
  return cloneSnapshot({
    scenes: state.scenes,
    sceneOrder: state.sceneOrder,
    subtitleStyle: state.subtitleStyle,
    voiceConfig: state.voiceConfig,
    musicAssetId: state.musicAssetId,
    musicVolume: state.musicVolume,
    overlays: state.overlays,
  })
}

export function describeRevisionChanges(
  previous: RevisionSnapshot,
  current: RevisionSnapshot,
): string[] {
  const changes: string[] = []
  if (!sameValue(previous.scenes, current.scenes)) {
    const changedScenes = current.scenes.filter((scene, index) => (
      !sameValue(scene, previous.scenes[index])
    )).length
    changes.push(`Texto: ${changedScenes} cena${changedScenes === 1 ? '' : 's'} alterada${changedScenes === 1 ? '' : 's'}`)
  }
  if (!sameValue(previous.sceneOrder, current.sceneOrder)) {
    changes.push(`Ordem das cenas: ${current.sceneOrder.map((index) => index + 1).join(' → ')}`)
  }
  if (previous.subtitleStyle.preset !== current.subtitleStyle.preset) {
    changes.push(`Legendas: ${titleCase(current.subtitleStyle.preset)}`)
  }
  if (previous.musicAssetId !== current.musicAssetId) {
    changes.push(`Trilha: ${current.musicAssetId ? MUSIC_LABELS[current.musicAssetId] ?? current.musicAssetId : 'Sem música'}`)
  }
  if (previous.musicVolume !== current.musicVolume) {
    changes.push(`Volume da trilha: ${Math.round(current.musicVolume * 100)}%`)
  }
  if (!sameValue(previous.voiceConfig, current.voiceConfig)) {
    changes.push(`Voz: ${current.voiceConfig.voiceId} (${titleCase(current.voiceConfig.voiceProvider)})`)
  }
  if (!sameValue(previous.overlays, current.overlays)) {
    changes.push(`Elementos: ${current.overlays.length}`)
  }
  return changes.length > 0 ? changes : ['Ajustes do editor confirmados']
}

export function formatRenderElapsed(startedAt: string | null, nowMs = Date.now()): string {
  const startedMs = startedAt ? Date.parse(startedAt) : Number.NaN
  const elapsedSeconds = Number.isFinite(startedMs)
    ? Math.max(0, Math.floor((nowMs - startedMs) / 1000))
    : 0
  const hours = Math.floor(elapsedSeconds / 3600)
  const minutes = Math.floor((elapsedSeconds % 3600) / 60)
  const seconds = elapsedSeconds % 60
  const clock = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  return hours > 0 ? `${hours}:${clock}` : clock
}

function isRevision(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0
}

export function normalizeRenderRevision(
  saved: Partial<RenderRevisionState> | undefined,
  hasSavedEditorState: boolean,
): RenderRevisionState {
  const fallbackRevision = hasSavedEditorState ? 1 : 0
  const editRevision = saved?.editRevision
  const renderedRevision = saved?.renderedRevision
  const renderingRevision = saved?.renderingRevision
  const hasValidContract = isRevision(editRevision)
    && isRevision(renderedRevision)
    && renderedRevision <= editRevision
    && (
      renderingRevision === null
      || (
        isRevision(renderingRevision)
        && renderingRevision >= renderedRevision
        && renderingRevision <= editRevision
      )
    )

  if (!hasValidContract) {
    return {
      editRevision: fallbackRevision,
      renderedRevision: 0,
      renderingRevision: null,
      renderedAt: null,
    }
  }

  return {
    editRevision,
    renderedRevision,
    renderingRevision,
    renderedAt: typeof saved?.renderedAt === 'string' && saved.renderedAt
      ? saved.renderedAt
      : null,
  }
}

export function hasUnrenderedChanges(state: RenderRevisionState): boolean {
  return state.editRevision !== state.renderedRevision
}

export function nextEditRevision<T extends RenderRevisionState>(state: T): T {
  return { ...state, editRevision: state.editRevision + 1 }
}

export function beginRenderRevision<T extends RenderRevisionState>(state: T): T {
  return { ...state, renderingRevision: state.editRevision }
}

export function completeRenderRevision<T extends RenderRevisionState>(
  state: T,
  renderedAt: string,
): T {
  return {
    ...state,
    renderedRevision: state.renderingRevision ?? state.editRevision,
    renderingRevision: null,
    renderedAt,
  }
}

export function normalizeRevisionTimeline(
  saved: Partial<CompositionData> | undefined,
  baseSnapshot: RevisionSnapshot,
  revision: RenderRevisionState,
  currentSnapshot?: RevisionSnapshot,
): Pick<CompositionData, 'renderStartedAt' | 'renderedSnapshot' | 'revisionHistory'> {
  const rawHistory = Array.isArray(saved?.revisionHistory) ? saved.revisionHistory : []
  const history: RenderRevisionEntry[] = rawHistory.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object') return []
    const entry = candidate as Partial<RenderRevisionEntry>
    if (
      !isRevision(entry.revision)
      || typeof entry.author !== 'string'
      || !['rendering', 'completed'].includes(entry.status ?? '')
      || !Array.isArray(entry.changes)
      || entry.changes.some((change) => typeof change !== 'string')
      || !isSnapshot(entry.snapshot)
    ) {
      return []
    }
    return [{
      revision: entry.revision,
      author: entry.author.slice(0, 120),
      startedAt: normalizeIso(entry.startedAt),
      renderedAt: normalizeIso(entry.renderedAt),
      status: entry.status as RenderRevisionEntry['status'],
      restorable: entry.restorable !== false,
      changes: entry.changes.slice(0, 12),
      snapshot: cloneSnapshot(entry.snapshot),
    }]
  }).slice(-MAX_RENDER_HISTORY)

  const alignedLegacySnapshot = revision.editRevision === revision.renderedRevision && isSnapshot(currentSnapshot)
    ? cloneSnapshot(currentSnapshot)
    : null

  if (history.length === 0) {
    history.push({
      revision: revision.renderedRevision,
      author: revision.renderedRevision === 0 ? 'ClipIA' : 'Histórico anterior',
      startedAt: null,
      renderedAt: revision.renderedAt,
      status: 'completed',
      restorable: revision.renderedRevision === 0 || alignedLegacySnapshot !== null,
      changes: revision.renderedRevision === 0
        ? ['Versão original gerada pela ClipIA']
        : ['Detalhes desta revisão não estavam registrados'],
      snapshot: alignedLegacySnapshot ?? cloneSnapshot(baseSnapshot),
    })
  }

  const latestCompleted = [...history].reverse().find((entry) => entry.status === 'completed')
  const renderedSnapshot = isSnapshot(saved?.renderedSnapshot)
    ? cloneSnapshot(saved.renderedSnapshot)
    : cloneSnapshot(latestCompleted?.snapshot ?? baseSnapshot)

  return {
    renderStartedAt: revision.renderingRevision === null ? null : normalizeIso(saved?.renderStartedAt),
    renderedSnapshot,
    revisionHistory: history,
  }
}

export function startRenderRevision(
  state: CompositionData,
  options: { author: string; startedAt: string },
): CompositionData {
  const started = beginRenderRevision(state)
  const snapshot = snapshotRevision(state)
  const receipt: RenderRevisionEntry = {
    revision: state.editRevision,
    author: options.author.trim().slice(0, 120) || 'Você',
    startedAt: options.startedAt,
    renderedAt: null,
    status: 'rendering',
    restorable: true,
    changes: describeRevisionChanges(state.renderedSnapshot, snapshot),
    snapshot,
  }
  const withoutStaleAttempt = state.revisionHistory.filter((entry) => (
    !(entry.revision === receipt.revision && entry.status === 'rendering')
  ))
  return {
    ...started,
    renderStartedAt: options.startedAt,
    revisionHistory: [...withoutStaleAttempt, receipt].slice(-MAX_RENDER_HISTORY),
  }
}

export function finishRenderRevision(
  state: CompositionData,
  renderedAt: string,
): CompositionData {
  const revision = state.renderingRevision ?? state.editRevision
  const existing = state.revisionHistory.find((entry) => entry.revision === revision && entry.status === 'rendering')
  const snapshot = cloneSnapshot(existing?.snapshot ?? snapshotRevision(state))
  const completedEntry: RenderRevisionEntry = {
    revision,
    author: existing?.author ?? 'Você',
    startedAt: existing?.startedAt ?? state.renderStartedAt,
    renderedAt,
    status: 'completed',
    restorable: true,
    changes: existing?.changes ?? describeRevisionChanges(state.renderedSnapshot, snapshot),
    snapshot,
  }
  const history = state.revisionHistory
    .filter((entry) => !(entry.revision === revision && entry.status === 'rendering'))
    .concat(completedEntry)
    .slice(-MAX_RENDER_HISTORY)
  return {
    ...completeRenderRevision(state, renderedAt),
    renderStartedAt: null,
    renderedSnapshot: snapshot,
    revisionHistory: history,
  }
}

export function restoreRevision(state: CompositionData, revision: number): CompositionData {
  const entry = [...state.revisionHistory]
    .reverse()
    .find((candidate) => (
      candidate.revision === revision
      && candidate.status === 'completed'
      && candidate.restorable
    ))
  if (!entry) return state
  const snapshot = cloneSnapshot(entry.snapshot)
  const physicalMedia = [...state.mediaUrls]
  state.sceneOrder.forEach((originalIndex, currentIndex) => {
    if (state.mediaUrls[currentIndex] !== undefined) physicalMedia[originalIndex] = state.mediaUrls[currentIndex]
  })
  return {
    ...state,
    ...snapshot,
    mediaUrls: snapshot.sceneOrder
      .map((originalIndex, currentIndex) => physicalMedia[originalIndex] ?? state.mediaUrls[currentIndex])
      .filter((url): url is string => typeof url === 'string'),
    editRevision: state.editRevision + 1,
    renderingRevision: null,
    renderStartedAt: null,
    narrationStale: true,
  }
}
