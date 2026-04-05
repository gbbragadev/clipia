'use client'

import { useEffect } from 'react'
import { RouteErrorScreen } from '@/components/ui/feedback'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <html lang="pt-BR">
      <body>
        <RouteErrorScreen
          title="Erro critico da aplicacao"
          description="A interface encontrou uma falha global. Tente recarregar a pagina."
          onRetry={reset}
          homeHref="/"
          homeLabel="Ir para a home"
        />
      </body>
    </html>
  )
}
