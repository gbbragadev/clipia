import type { CompositionData, Scene } from '@/remotion/types'

export const MIN_TIMELINE_ZOOM = 1
export const MAX_TIMELINE_ZOOM = 3

export function clampTimelineZoom(value: number): number {
  return Math.min(MAX_TIMELINE_ZOOM, Math.max(MIN_TIMELINE_ZOOM, value))
}

export function identitySceneOrder(count: number): number[] {
  return Array.from({ length: Math.max(0, count) }, (_, index) => index)
}

export function normalizeSceneOrder(value: unknown, count: number): number[] {
  const identity = identitySceneOrder(count)
  if (!Array.isArray(value) || value.length !== count) return identity
  if (!value.every((item) => typeof item === 'number' && Number.isInteger(item))) {
    return identity
  }

  const order = value as number[]
  const isPermutation = [...order]
    .sort((a, b) => a - b)
    .every((item, index) => item === identity[index])
  return isPermutation ? [...order] : identity
}

export function getSceneSpans(scenes: Scene[]): Array<{
  start: number
  end: number
  duration: number
}> {
  const total = scenes.reduce(
    (sum, scene) => sum + Math.max(0, scene.duration_hint),
    0,
  ) || 1
  let cursor = 0

  return scenes.map((scene) => {
    const duration = Math.max(0, scene.duration_hint)
    const start = cursor / total
    cursor += duration
    return { start, end: cursor / total, duration }
  })
}

function move<T>(items: T[], from: number, to: number): T[] {
  const copy = [...items]
  const [item] = copy.splice(from, 1)
  copy.splice(to, 0, item)
  return copy
}

export function reorderComposition(
  composition: CompositionData,
  from: number,
  to: number,
): CompositionData {
  const sceneCount = composition.scenes.length
  if (
    from === to
    || from < 0
    || to < 0
    || from >= sceneCount
    || to >= sceneCount
  ) {
    return composition
  }

  const sceneOrder = normalizeSceneOrder(composition.sceneOrder, sceneCount)
  return {
    ...composition,
    scenes: move(composition.scenes, from, to),
    mediaUrls: composition.mediaUrls.length === sceneCount
      ? move(composition.mediaUrls, from, to)
      : composition.mediaUrls,
    sceneOrder: move(sceneOrder, from, to),
    narrationStale: true,
  }
}
