'use client'

import { useEffect } from 'react'
import { RouteErrorScreen } from '@/components/ui/feedback'

export default function Error({
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
    <RouteErrorScreen
      title="Não foi possível carregar esta página"
      description="Ocorreu um erro inesperado durante o carregamento. Voce pode tentar novamente ou voltar para a home."
      onRetry={reset}
    />
  )
}
