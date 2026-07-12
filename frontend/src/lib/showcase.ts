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

export async function loadShowcase(): Promise<ShowcaseManifest> {
  const res = await fetch('/showcase/showcase.json')
  if (!res.ok) throw new Error(`showcase.json: ${res.status}`)
  return res.json()
}
