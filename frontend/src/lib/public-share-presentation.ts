import type { Metadata } from 'next'

const SITE_URL = 'https://clipia.com.br'
const PUBLIC_TITLE = 'Vídeo publicado com ClipIA'
const PUBLIC_DESCRIPTION = 'Assista a um vídeo publicado por um criador com o ClipIA e transforme sua própria ideia em vídeo.'

export interface SharePresentationInput {
  kind: 'showcase' | 'public'
  id: string
  title: string
  template: string
  niche: string
  video: string
}

function absoluteUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  return `${SITE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

function publicVideoPath(id: string): string {
  return `/api/v1/public-shares/${encodeURIComponent(id)}/video`
}

export function getShareDisplayTitle(input: SharePresentationInput): string {
  return input.kind === 'showcase' ? input.title : PUBLIC_TITLE
}

export function buildShareMetadata(input: SharePresentationInput): Metadata {
  const isShowcase = input.kind === 'showcase'
  const displayTitle = getShareDisplayTitle(input)
  const title = isShowcase ? `${displayTitle} — feito com ClipIA` : displayTitle
  const description = isShowcase
    ? 'Vídeo vertical gerado e editado no ClipIA: roteiro, narração em português e legendas sincronizadas. Crie o seu grátis.'
    : PUBLIC_DESCRIPTION
  const pageUrl = absoluteUrl(`/v/${encodeURIComponent(input.id)}`)
  const videoUrl = absoluteUrl(isShowcase ? input.video : publicVideoPath(input.id))
  const ogImage = isShowcase ? `/showcase/og/${encodeURIComponent(input.id)}.jpg` : '/og-image.png'
  const imageAlt = displayTitle

  return {
    title,
    description,
    alternates: { canonical: pageUrl },
    openGraph: {
      title,
      description,
      type: 'video.other',
      url: pageUrl,
      siteName: 'ClipIA',
      locale: 'pt_BR',
      images: [{ url: ogImage, width: 1200, height: 630, alt: imageAlt }],
      videos: [{ url: videoUrl, type: 'video/mp4' }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [ogImage],
    },
  }
}

export function buildShareJsonLd(input: SharePresentationInput): Record<string, unknown> {
  const isShowcase = input.kind === 'showcase'
  return {
    '@context': 'https://schema.org',
    '@type': 'VideoObject',
    name: getShareDisplayTitle(input),
    description: isShowcase
      ? `Vídeo vertical de ${input.niche} gerado e editado no ClipIA (template ${input.template}).`
      : PUBLIC_DESCRIPTION,
    thumbnailUrl: absoluteUrl(isShowcase ? `/showcase/og/${encodeURIComponent(input.id)}.jpg` : '/og-image.png'),
    contentUrl: absoluteUrl(isShowcase ? input.video : publicVideoPath(input.id)),
    ...(isShowcase ? { uploadDate: '2026-04-04' } : {}),
    inLanguage: 'pt-BR',
  }
}
