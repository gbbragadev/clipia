import assert from 'node:assert/strict'
import test from 'node:test'

import {
  beginRenderRevision,
  completeRenderRevision,
  hasUnrenderedChanges,
  nextEditRevision,
  normalizeRenderRevision,
} from './editor-render-revision.ts'

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
