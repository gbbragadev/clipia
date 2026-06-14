'use client'

import { Suspense, useEffect, useState, type ReactNode } from 'react'
import { AuthProvider } from '@/contexts/AuthContext'
import { OfflineBanner, ToastProvider, useToast } from '@/components/ui/feedback'
import { useUTM } from '@/hooks/useUTM'

// Captura UTM/ref como side-effect puro. NAO deve envolver `children`: useUTM usa
// useSearchParams, e se a arvore de conteudo ficar dentro do <Suspense fallback={null}>
// dela, todo o body renderiza `null` no servidor (SSR) e so aparece apos hidratacao —
// matando o SEO. Por isso fica isolado, sem filhos.
function UTMCapture() {
  useUTM()
  return null
}

function NetworkStatusBridge({ children }: { children: ReactNode }) {
  const [online, setOnline] = useState(true)
  const { info, success, error } = useToast()

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    update()

    const handleOnline = () => {
      setOnline(true)
      success('Conexao restaurada', 'Os recursos interativos voltaram a funcionar normalmente.')
    }

    const handleOffline = () => {
      setOnline(false)
      error('Voce esta offline', 'Algumas acoes podem falhar ate a conexao voltar.')
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    if (!navigator.onLine) {
      info('Modo offline', 'O app segue acessivel, mas algumas requisicoes podem falhar.')
    }

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [error, info, success])

  return (
    <>
      <OfflineBanner online={online} />
      {children}
    </>
  )
}

export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <NetworkStatusBridge>
        {/* useSearchParams isolado num Suspense proprio (exigencia do Next), sem envolver
            o conteudo — assim `children` renderiza no servidor (SSR/SSG) e o Google indexa. */}
        <Suspense fallback={null}>
          <UTMCapture />
        </Suspense>
        <AuthProvider>{children}</AuthProvider>
      </NetworkStatusBridge>
    </ToastProvider>
  )
}
