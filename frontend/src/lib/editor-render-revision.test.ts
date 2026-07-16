import assert from 'node:assert/strict'
import test from 'node:test'
import type { CompositionData, RevisionSnapshot } from '../remotion/types.ts'
import * as revisionModule from './editor-render-revision.ts'

import {
  beginRenderRevision,
  completeRenderRevision,
  hasUnrenderedChanges,
  nextEditRevision,
  normalizeRenderRevision,
  normalizeRevisionTimeline,
} from './editor-render-revision.ts'

const futureRevision = revisionModule as unknown as Record<string, unknown>

const BASE_SNAPSHOT: RevisionSnapshot = {
  scenes: [
    { text: 'Cena A', keywords_en: ['brain'], duration_hint: 2 },
    { text: 'Cena B', keywords_en: ['memory'], duration_hint: 3 },
  ],
  sceneOrder: [0, 1],
  subtitleStyle: {
    fontFamily: 'Montserrat, sans-serif',
    fontSize: 52,
    color: '#FFFFFF',
    outlineColor: '#000000',
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    position: 'bottom',
    marginBottom: 180,
    maxWordsPerChunk: 3,
    preset: 'minimal',
    accentColor: '#FFFC00',
    strokeWidth: 0,
    animationStyle: 'pop',
  },
  voiceConfig: {
    voiceId: 'pt-BR-AntonioNeural',
    voiceProvider: 'edge',
    rate: -10,
    pitch: 5,
  },
  musicAssetId: null,
  musicVolume: 0.12,
  overlays: [],
}

function compositionWithPendingChanges(): CompositionData {
  return {
    ...structuredClone(BASE_SNAPSHOT),
    sceneOrder: [1, 0],
    subtitleStyle: { ...BASE_SNAPSHOT.subtitleStyle, preset: 'karaoke' },
    voiceConfig: {
      voiceId: 'pt-BR-FranciscaNeural',
      voiceProvider: 'edge',
      rate: 0,
      pitch: 0,
    },
    musicAssetId: 'lofi-chill',
    musicVolume: 0.35,
    overlays: [{ type: 'followCTA', startFrame: 0, endFrame: 30, config: {} }],
    narrationStale: false,
    words: [],
    audioUrl: '/audio.wav',
    mediaUrls: ['/a.mp4', '/b.mp4'],
    fps: 30,
    width: 1080,
    height: 1920,
    title: 'Teste',
    editRevision: 1,
    renderedRevision: 0,
    renderingRevision: null,
    renderedAt: '2026-07-15T12:00:00.000Z',
    renderStartedAt: null,
    renderedSnapshot: structuredClone(BASE_SNAPSHOT),
    revisionHistory: [{
      revision: 0,
      author: 'ClipIA',
      startedAt: '2026-07-15T11:59:00.000Z',
      renderedAt: '2026-07-15T12:00:00.000Z',
      status: 'completed',
      restorable: true,
      changes: ['Versão original gerada pela ClipIA'],
      snapshot: structuredClone(BASE_SNAPSHOT),
    }],
  }
}

test('a fresh composition starts aligned with the generated video', () => {
  assert.deepEqual(normalizeRenderRevision(undefined, false), {
    editRevision: 0,
    renderedRevision: 0,
    renderingRevision: null,
    renderedAt: null,
  })
})

test('legacy saved editor state is conservatively treated as pending', () => {
  const revision = normalizeRenderRevision({}, true)

  assert.equal(revision.editRevision, 1)
  assert.equal(revision.renderedRevision, 0)
  assert.equal(hasUnrenderedChanges(revision), true)
})

test('editing, starting and completing a render preserve exact revision identity', () => {
  const initial = normalizeRenderRevision(undefined, false)
  const edited = nextEditRevision(initial)
  const rendering = beginRenderRevision(edited)
  const completed = completeRenderRevision(rendering, '2026-07-15T12:00:00.000Z')

  assert.equal(edited.editRevision, 1)
  assert.equal(hasUnrenderedChanges(edited), true)
  assert.equal(rendering.renderingRevision, 1)
  assert.deepEqual(completed, {
    editRevision: 1,
    renderedRevision: 1,
    renderingRevision: null,
    renderedAt: '2026-07-15T12:00:00.000Z',
  })
  assert.equal(hasUnrenderedChanges(completed), false)
})

test('an edit made during rendering remains pending after that render completes', () => {
  const rendering = beginRenderRevision(nextEditRevision(normalizeRenderRevision(undefined, false)))
  const editedAgain = nextEditRevision(rendering)
  const completed = completeRenderRevision(editedAgain, '2026-07-15T12:00:00.000Z')

  assert.equal(completed.renderedRevision, 1)
  assert.equal(completed.editRevision, 2)
  assert.equal(hasUnrenderedChanges(completed), true)
})

test('invalid persisted values normalize without inventing a completed render', () => {
  assert.deepEqual(normalizeRenderRevision({
    editRevision: -2,
    renderedRevision: 9,
    renderingRevision: -1,
    renderedAt: 123 as unknown as string,
  }, true), {
    editRevision: 1,
    renderedRevision: 0,
    renderingRevision: null,
    renderedAt: null,
  })
})

test('legacy rendered revisions never invent an original receipt', () => {
  const timeline = normalizeRevisionTimeline({ renderedRevision: 3 }, BASE_SNAPSHOT, {
    editRevision: 3,
    renderedRevision: 3,
    renderingRevision: null,
    renderedAt: '2026-07-15T12:00:00.000Z',
  })

  assert.equal(timeline.revisionHistory[0].author, 'Histórico anterior')
  assert.deepEqual(timeline.revisionHistory[0].changes, ['Detalhes desta revisão não estavam registrados'])
  assert.equal(timeline.revisionHistory[0].restorable, false)
})

test('an aligned legacy state becomes the trustworthy baseline for future receipts', () => {
  const currentSnapshot: RevisionSnapshot = {
    ...structuredClone(BASE_SNAPSHOT),
    musicAssetId: 'lofi-chill',
    musicVolume: 0.35,
  }
  const timeline = normalizeRevisionTimeline(
    { renderedRevision: 3 },
    BASE_SNAPSHOT,
    {
      editRevision: 3,
      renderedRevision: 3,
      renderingRevision: null,
      renderedAt: '2026-07-15T12:00:00.000Z',
    },
    currentSnapshot,
  )

  assert.equal(timeline.revisionHistory[0].author, 'Histórico anterior')
  assert.deepEqual(timeline.revisionHistory[0].changes, ['Detalhes desta revisão não estavam registrados'])
  assert.equal(timeline.revisionHistory[0].restorable, true)
  assert.deepEqual(timeline.renderedSnapshot, currentSnapshot)
})

test('elapsed render time is honest and supports durations over one hour', () => {
  const formatter = futureRevision.formatRenderElapsed
  assert.equal(typeof formatter, 'function')
  const formatRenderElapsed = formatter as (startedAt: string | null, nowMs: number) => string

  assert.equal(formatRenderElapsed('2026-07-15T12:00:00.000Z', Date.parse('2026-07-15T12:02:05.000Z')), '02:05')
  assert.equal(formatRenderElapsed('2026-07-15T12:00:00.000Z', Date.parse('2026-07-15T13:01:01.000Z')), '1:01:01')
  assert.equal(formatRenderElapsed(null, Date.now()), '00:00')
})

test('starting a render stores an exact receipt and completing it preserves the revision', () => {
  const starter = futureRevision.startRenderRevision
  const finisher = futureRevision.finishRenderRevision
  assert.equal(typeof starter, 'function')
  assert.equal(typeof finisher, 'function')
  const startRenderRevision = starter as (
    state: CompositionData,
    options: { author: string; startedAt: string },
  ) => CompositionData
  const finishRenderRevision = finisher as (state: CompositionData, renderedAt: string) => CompositionData

  const started = startRenderRevision(compositionWithPendingChanges(), {
    author: 'Editor QA',
    startedAt: '2026-07-15T12:05:00.000Z',
  })
  const receipt = started.revisionHistory.at(-1)

  assert.equal(started.renderingRevision, 1)
  assert.equal(started.renderStartedAt, '2026-07-15T12:05:00.000Z')
  assert.equal(receipt?.revision, 1)
  assert.equal(receipt?.author, 'Editor QA')
  assert.equal(receipt?.status, 'rendering')
  assert.deepEqual(receipt?.changes, [
    'Ordem das cenas: 2 → 1',
    'Legendas: Karaoke',
    'Trilha: Lo-Fi Chill',
    'Volume da trilha: 35%',
    'Voz: pt-BR-FranciscaNeural (Edge)',
    'Elementos: 1',
  ])

  const finished = finishRenderRevision(started, '2026-07-15T12:10:00.000Z')
  assert.equal(finished.renderedRevision, 1)
  assert.equal(finished.renderStartedAt, null)
  assert.deepEqual(finished.renderedSnapshot, receipt?.snapshot)
  assert.equal(finished.revisionHistory.at(-1)?.status, 'completed')
  assert.equal(finished.revisionHistory.at(-1)?.renderedAt, '2026-07-15T12:10:00.000Z')
})

test('revision history keeps five entries and a restore creates pending safe narration state', () => {
  const starter = futureRevision.startRenderRevision
  const restorer = futureRevision.restoreRevision
  assert.equal(typeof starter, 'function')
  assert.equal(typeof restorer, 'function')
  const startRenderRevision = starter as (
    state: CompositionData,
    options: { author: string; startedAt: string },
  ) => CompositionData
  const restoreRevision = restorer as (state: CompositionData, revision: number) => CompositionData

  const state = compositionWithPendingChanges()
  state.editRevision = 5
  state.renderedRevision = 4
  state.revisionHistory = Array.from({ length: 5 }, (_, revision) => ({
    revision,
    author: 'Editor QA',
    startedAt: `2026-07-15T12:0${revision}:00.000Z`,
    renderedAt: `2026-07-15T12:0${revision}:30.000Z`,
    status: 'completed' as const,
    restorable: true,
    changes: [`Revisão ${revision}`],
    snapshot: structuredClone(revision === 0 ? BASE_SNAPSHOT : {
      ...BASE_SNAPSHOT,
      musicAssetId: 'lofi-chill' as const,
    }),
  }))

  const started = startRenderRevision(state, {
    author: 'Editor QA',
    startedAt: '2026-07-15T12:10:00.000Z',
  })
  assert.deepEqual(started.revisionHistory.map((entry) => entry.revision), [1, 2, 3, 4, 5])

  const restored = restoreRevision(started, 1)
  assert.equal(restored.musicAssetId, 'lofi-chill')
  assert.deepEqual(restored.mediaUrls, ['/b.mp4', '/a.mp4'])
  assert.equal(restored.narrationStale, true)
  assert.equal(restored.editRevision, 6)
  assert.equal(restored.renderingRevision, null)
})
