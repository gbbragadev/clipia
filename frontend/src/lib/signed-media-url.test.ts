import assert from 'node:assert/strict'
import test from 'node:test'

import { withCacheBuster } from './signed-media-url.ts'

test('cache buster preserves an existing signed query string', () => {
  assert.equal(
    withCacheBuster('/storage/narration.wav?exp=123&sig=abc', 456),
    '/storage/narration.wav?exp=123&sig=abc&t=456',
  )
})

test('cache buster starts a query string when none exists', () => {
  assert.equal(
    withCacheBuster('/storage/narration.wav', 456),
    '/storage/narration.wav?t=456',
  )
})
