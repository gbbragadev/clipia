import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Criar conta | ClipIA',
  description: 'Crie sua conta grátis e ganhe créditos de boas-vindas para gerar seus primeiros vídeos com IA.',
  // Página utilitária: fora do índice (e do sitemap) — o crawl vai para landing/nichos/blog.
  robots: { index: false, follow: false },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
