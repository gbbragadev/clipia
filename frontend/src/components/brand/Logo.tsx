'use client'

import { strings } from '@/lib/strings';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
}

// Logo unico do ClipIA (identidade coral/grafite). Usado em landing, dashboard,
// editor e auth — um logo so. Marca: quadrado arredondado com play coral + ponto
// mint, wordmark Clip(cloud)+IA(coral).
const sizes = {
  sm: { box: 'h-7 w-7', icon: 'h-3 w-3', text: 'text-base', dot: 'h-1 w-1 bottom-1 right-1' },
  md: { box: 'h-9 w-9', icon: 'h-4 w-4', text: 'text-xl', dot: 'h-1.5 w-1.5 bottom-1 right-1' },
  lg: { box: 'h-12 w-12', icon: 'h-5 w-5', text: 'text-3xl', dot: 'h-2 w-2 bottom-1.5 right-1.5' },
}

export default function Logo({ size = 'md', showText = true, className = '' }: LogoProps) {
  const s = sizes[size]
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span className={`relative grid ${s.box} place-items-center overflow-hidden rounded-xl border border-white/10 bg-white/[0.05]`}>
        <span className="absolute inset-0 bg-gradient-to-br from-coral/25 via-transparent to-azure/15" />
        <svg viewBox="0 0 24 24" className={`relative ${s.icon}`} aria-hidden="true">
          <path d="M8 5.2l10 6.8-10 6.8z" fill="#ff5638" />
        </svg>
        <span className={`absolute ${s.dot} rounded-full bg-mint`} />
      </span>
      {showText && (
        <span className={`${s.text} font-bold tracking-tight`} style={{ fontFamily: 'var(--font-display), system-ui, sans-serif' }}>
          <span style={{ color: 'var(--logo-text)' }}>Clip</span>
          <span className="text-coral">{strings.editor.ai}</span>
        </span>
      )}
    </span>
  )
}
