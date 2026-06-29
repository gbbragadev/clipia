'use client'

import { useEffect, useState } from 'react'
import { loadShowcase, type ShowcaseVideo } from '@/lib/showcase'
import { ShowcaseCard } from './ShowcaseSection'

// Galeria de exemplos filtrada por nicho, reusando ShowcaseCard. Carrega o manifesto no
// client (os videos nao sao conteudo textual SEO — o texto da pagina ja e SSR/SSG).
// Se o nicho ainda nao tem video, nao renderiza nada (a secao some).
export function NicheGallery({ niche }: { niche: string }) {
  const [videos, setVideos] = useState<ShowcaseVideo[] | null>(null)

  useEffect(() => {
    loadShowcase()
      .then((m) => setVideos(m.videos.filter((v) => v.niche === niche)))
      .catch(() => setVideos([]))
  }, [niche])

  if (!videos || videos.length === 0) return null

  return (
    <div className="flex md:grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-x-auto md:overflow-visible snap-x snap-mandatory px-4 md:px-0 overscroll-x-contain scroll-px-4 [&>*]:w-[80vw] md:[&>*]:w-auto [&>*]:shrink-0 md:[&>*]:shrink">
      {videos.map((item) => (
        <ShowcaseCard key={item.id} item={item} />
      ))}
    </div>
  )
}
