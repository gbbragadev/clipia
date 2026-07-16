import assert from 'node:assert/strict'
import test from 'node:test'

import {
  clampTimelineZoom,
  getSceneSpans,
  normalizeSceneOrder,
  reorderComposition,
} from './editor-timeline.ts'

const composition = {
  scenes: [
    { text: 'A', keywords_en: [], duration_hint: 2 },
    { text: 'B', keywords_en: [], duration_hint: 3 },
    { text: 'C', keywords_en: [], duration_hint: 5 },
  ],
  mediaUrls: ['m0', 'm1', 'm2'],
  sceneOrder: [0, 1, 2],
} as any

test('reorder keeps scenes, media and physical order aligned', () => {
  const next = reorderComposition(composition, 2, 0)

  assert.deepEqual(next.scenes.map((scene: any) => scene.text), ['C', 'A', 'B'])
  assert.deepEqual(next.mediaUrls, ['m2', 'm0', 'm1'])
  assert.deepEqual(next.sceneOrder, [2, 0, 1])
  assert.equal(next.narrationStale, true)
  assert.deepEqual(composition.sceneOrder, [0, 1, 2])
})

test('invalid and no-op reorder return the original object', () => {
  assert.equal(reorderComposition(composition, -1, 0), composition)
  assert.equal(reorderComposition(composition, 1, 1), composition)
  assert.equal(reorderComposition(composition, 0, 3), composition)
})

test('legacy and invalid scene orders normalize to identity', () => {
  assert.deepEqual(normalizeSceneOrder(undefined, 3), [0, 1, 2])
  assert.deepEqual(normalizeSceneOrder([0, 0, 2], 3), [0, 1, 2])
  assert.deepEqual(normalizeSceneOrder([2, 0, 1], 3), [2, 0, 1])
})

test('zoom and spans are bounded and proportional', () => {
  assert.equal(clampTimelineZoom(0.1), 1)
  assert.equal(clampTimelineZoom(9), 3)
  assert.deepEqual(getSceneSpans(composition.scenes), [
    { start: 0, end: 0.2, duration: 2 },
    { start: 0.2, end: 0.5, duration: 3 },
    { start: 0.5, end: 1, duration: 5 },
  ])
})
