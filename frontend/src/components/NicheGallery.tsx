import Link from 'next/link'
import type { ShowcaseVideo } from '@/lib/showcase'
import { ShowcaseCard } from './ShowcaseSection'

// O catálogo canônico é resolvido no servidor e chega pronto no HTML inicial. Isso
// evita uma grade vazia durante hydration e mantém nichos/galeria na mesma fonte.
export function NicheGallery({ videos }: { videos: ShowcaseVideo[] }) {
  if (videos.length === 0) {
    return (
      <div className="text-center">
        <Link
          href="/exemplos"
          className="inline-flex rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-coral-soft transition hover:bg-white/10"
        >
          Ver todos os exemplos
        </Link>
      </div>
    )
  }

  return (
    <div data-niche-video-grid className="flex md:grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-x-auto md:overflow-visible snap-x snap-mandatory px-4 md:px-0 overscroll-x-contain scroll-px-4 [&>*]:w-[80vw] md:[&>*]:w-auto [&>*]:shrink-0 md:[&>*]:shrink">
      {videos.map((item) => (
        <ShowcaseCard key={item.id} item={item} />
      ))}
    </div>
  )
}
