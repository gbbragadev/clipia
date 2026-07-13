import showcaseManifest from "../../public/showcase/showcase.json";

export interface ShowcaseNiche {
  id: string
  label: string
  icon: string
}

export interface ShowcaseVideo {
  id: string
  title: string
  template: string
  niche: string
  video: string
  /** Frame real do vídeo (jpg): pintura imediata nos cards (preload="none"). */
  poster?: string
  phrase: string
  captionStyle: 'tiktok' | 'impact' | 'karaoke' | 'minimal' | 'boxed'
  captionAccent: string
  gradient: string
  icon: string
  hero?: boolean
  beforeScript?: string
}

export interface ShowcaseManifest {
  niches: ShowcaseNiche[]
  videos: ShowcaseVideo[]
}

export const SHOWCASE_CATALOG = showcaseManifest as unknown as ShowcaseManifest

const CAPTION_STYLES = new Set<ShowcaseVideo['captionStyle']>([
  'tiktok',
  'impact',
  'karaoke',
  'minimal',
  'boxed',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isOwnedAssetPath(value: unknown): value is string {
  return isNonEmptyString(value) && value.startsWith('/') && !value.startsWith('//')
}

function isShowcaseNiche(value: unknown): value is ShowcaseNiche {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isNonEmptyString(value.label) &&
    isNonEmptyString(value.icon)
  )
}

function isShowcaseVideo(value: unknown): value is ShowcaseVideo {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isNonEmptyString(value.title) &&
    isNonEmptyString(value.template) &&
    isNonEmptyString(value.niche) &&
    isOwnedAssetPath(value.video) &&
    (value.poster === undefined || isOwnedAssetPath(value.poster)) &&
    isNonEmptyString(value.phrase) &&
    isNonEmptyString(value.captionStyle) &&
    CAPTION_STYLES.has(value.captionStyle as ShowcaseVideo['captionStyle']) &&
    isNonEmptyString(value.captionAccent) &&
    isNonEmptyString(value.gradient) &&
    isNonEmptyString(value.icon) &&
    (value.hero === undefined || typeof value.hero === 'boolean') &&
    (value.beforeScript === undefined || typeof value.beforeScript === 'string')
  )
}

function isShowcaseManifest(value: unknown): value is ShowcaseManifest {
  return (
    isRecord(value) &&
    Array.isArray(value.niches) &&
    value.niches.every(isShowcaseNiche) &&
    Array.isArray(value.videos) &&
    value.videos.every(isShowcaseVideo)
  )
}

export function getShowcaseVideosForNiche(niche: string): ShowcaseVideo[] {
  return SHOWCASE_CATALOG.videos.filter((video) => video.niche === niche)
}

export async function loadShowcase(): Promise<ShowcaseManifest> {
  try {
    const response = await fetch('/showcase/showcase.json')
    if (!response.ok) return SHOWCASE_CATALOG

    const manifest: unknown = await response.json()
    return isShowcaseManifest(manifest) ? manifest : SHOWCASE_CATALOG
  } catch {
    return SHOWCASE_CATALOG
  }
}
