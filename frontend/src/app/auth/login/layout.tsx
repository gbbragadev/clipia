import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Entrar | ClipIA',
  description: 'Acesse sua conta ClipIA e comece a criar vídeos curtos com IA.',
  // Página utilitária: fora do índice (e do sitemap) — o crawl vai para landing/nichos/blog.
  robots: { index: false, follow: false },
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
