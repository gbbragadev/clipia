'use client'
import { useSyncExternalStore } from 'react'

const QUERY = '(max-width: 768px)'

function subscribe(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const mql = window.matchMedia(QUERY)
  mql.addEventListener('change', callback)
  return () => mql.removeEventListener('change', callback)
}

function getSnapshot(): boolean {
  return window.matchMedia(QUERY).matches
}

function getServerSnapshot(): boolean {
  // SSR/primeiro paint: assume desktop (evita layout-shift no editor desktop, que é o caso comum).
  return false
}

/** True quando a viewport é <= 768px. Atualiza ao redimensionar/girar o dispositivo. */
export function useIsMobile(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
