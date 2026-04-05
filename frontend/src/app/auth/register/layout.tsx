import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Criar conta | ClipIA',
  description: 'Crie sua conta grátis e ganhe 2 créditos para gerar seus primeiros vídeos com IA.',
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
