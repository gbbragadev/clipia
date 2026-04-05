import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Créditos | ClipIA',
  description: 'Compre créditos para gerar mais vídeos com IA.',
}

export default function CreditsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
