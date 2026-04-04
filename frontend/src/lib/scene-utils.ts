export function splitScenes(script: string): string[] {
  return script.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean)
}

export function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

export function sceneDensityRatio(
  sceneWords: number,
  wpm: number,
  totalDurationSec: number,
  numScenes: number,
): number {
  const budgetWords = (wpm / 60) * (totalDurationSec / numScenes)
  if (budgetWords === 0) return 0
  return sceneWords / budgetWords
}

export type DensityLevel = 'green' | 'amber' | 'red'

export function densityColor(ratio: number): DensityLevel {
  if (ratio < 0.72) return 'green'
  if (ratio < 1.08) return 'amber'
  return 'red'
}

export function densityLabel(level: DensityLevel): string {
  if (level === 'green') return 'folgado'
  if (level === 'amber') return 'ok'
  return 'apertado'
}

export function splitSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+/)
    .map(s => s.trim())
    .filter(Boolean)
}
