import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Recuperar senha | ClipIA',
  // Página utilitária: fora do índice — o crawl vai para landing/nichos/blog.
  robots: { index: false, follow: false },
}

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
