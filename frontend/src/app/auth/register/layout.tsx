import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Criar conta | ClipIA',
  description: 'Comece com 2 créditos grátis — até 2 vídeos com voz padrão. Sem cartão.',
  // Página utilitária: fora do índice (e do sitemap) — o crawl vai para landing/nichos/blog.
  robots: { index: false, follow: false },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
