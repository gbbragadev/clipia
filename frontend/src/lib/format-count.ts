export function nounForCount(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural
}

export function creditLabel(count: number): string {
  return nounForCount(count, 'crédito', 'créditos')
}

export function videoLabel(count: number): string {
  return nounForCount(count, 'vídeo', 'vídeos')
}
