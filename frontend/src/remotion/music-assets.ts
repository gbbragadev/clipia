import { staticFile } from 'remotion'

export const MUSIC_ASSET_IDS = [
  'lofi-chill',
  'upbeat-energy',
  'dramatic-epic',
  'ambient-calm',
  'cinematic-tension',
  'happy-pop',
  'dark-ambient',
  'inspirational',
  'dreamy-space',
  'tech-pulse',
] as const

export type MusicAssetId = (typeof MUSIC_ASSET_IDS)[number]

const MUSIC_ASSET_FILES: Record<MusicAssetId, string> = Object.fromEntries(
  MUSIC_ASSET_IDS.map((assetId) => [assetId, `music/${assetId}.mp3`]),
) as Record<MusicAssetId, string>

export function musicAssetUrl(assetId: MusicAssetId | null): string | null {
  return assetId ? staticFile(MUSIC_ASSET_FILES[assetId]) : null
}
