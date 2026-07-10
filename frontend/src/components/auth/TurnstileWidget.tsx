'use client'

import { useCallback, useEffect, useRef } from 'react'

// Cloudflare Turnstile (anti-bot). Graceful: sem NEXT_PUBLIC_TURNSTILE_SITE_KEY (baked no
// build), o componente nao renderiza e o cadastro segue sem captcha. Para ativar: gere as keys
// no painel Cloudflare, ponha a site key no .env.local do frontend e REBUILD (next build).
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY

interface TurnstileApi {
  render: (
    el: HTMLElement,
    opts: {
      sitekey: string
      callback: (token: string) => void
      'error-callback'?: () => void
      'expired-callback'?: () => void
      theme?: 'light' | 'dark' | 'auto'
      language?: string
    },
  ) => string
  reset: (id?: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

export function TurnstileWidget({ onToken }: { onToken: (token: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetId = useRef<string | null>(null)
  const onTokenRef = useRef(onToken)
  onTokenRef.current = onToken

  const renderWidget = useCallback(() => {
    if (!SITE_KEY || !containerRef.current || !window.turnstile || widgetId.current) return
    widgetId.current = window.turnstile.render(containerRef.current, {
      sitekey: SITE_KEY,
      theme: 'dark',
      language: 'pt-br', // widget no idioma do produto ("Verify you are human" era em ingles)
      callback: (token) => onTokenRef.current(token),
      'expired-callback': () => onTokenRef.current(''),
      'error-callback': () => onTokenRef.current(''),
    })
  }, [])

  useEffect(() => {
    if (!SITE_KEY) return
    if (window.turnstile) {
      renderWidget()
      return
    }
    let script = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`)
    if (!script) {
      script = document.createElement('script')
      script.src = SCRIPT_SRC
      script.async = true
      script.defer = true
      document.head.appendChild(script)
    }
    script.addEventListener('load', renderWidget)
    return () => script?.removeEventListener('load', renderWidget)
  }, [renderWidget])

  if (!SITE_KEY) return null
  return <div ref={containerRef} className="flex justify-center" />
}
