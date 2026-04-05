import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Entrar | ClipIA',
  description: 'Acesse sua conta ClipIA e comece a criar vídeos curtos com IA.',
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
