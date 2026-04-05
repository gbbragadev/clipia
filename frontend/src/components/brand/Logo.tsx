import { strings } from '@/lib/strings';
'use client'

interface LogoProps {
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
}

const sizes = {
  sm: { icon: 20, text: 'text-base', gap: 'gap-1.5' },
  md: { icon: 26, text: 'text-xl', gap: 'gap-2' },
  lg: { icon: 36, text: 'text-3xl', gap: 'gap-3' },
}

export default function Logo({ size = 'md', showText = true, className = '' }: LogoProps) {
  const s = sizes[size]

  return (
    <span className={`inline-flex items-center ${s.gap} ${className}`}>
      <LogoMark size={s.icon} />
      {showText && (
        <span className={`${s.text} font-bold tracking-tight`} style={{ fontFamily: 'var(--font-display), system-ui, sans-serif' }}>
          <span style={{ color: 'var(--logo-text)' }}>Clip</span>
          <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-blue-400 bg-clip-text text-transparent">{strings.editor.ai}</span>
        </span>
      )}
    </span>
  )
}

function LogoMark({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="logo-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8b5cf6" />
          <stop offset="50%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#3b82f6" />
        </linearGradient>
        <linearGradient id="logo-spark" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#c4b5fd" />
          <stop offset="100%" stopColor="#93c5fd" />
        </linearGradient>
      </defs>
      {/* Film frame — rounded with notches */}
      <rect x="3" y="3" width="34" height="34" rx="8" fill="url(#logo-grad)" />
      {/* Film perforations — left */}
      <rect x="6" y="9" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4" />
      <rect x="6" y="18" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4" />
      <rect x="6" y="27" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4" />
      {/* Film perforations — right */}
      <rect x="31" y="9" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4" />
      <rect x="31" y="18" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4" />
      <rect x="31" y="27" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4" />
      {/* Play triangle */}
      <polygon points="16,12 16,28 28,20" fill="white" opacity="0.95" />
      {/* AI sparkle — top right */}
      <circle cx="32" cy="8" r="3" fill="url(#logo-spark)" opacity="0.9" />
      <line x1="32" y1="4" x2="32" y2="12" stroke="white" strokeWidth="1" opacity="0.6" />
      <line x1="28" y1="8" x2="36" y2="8" stroke="white" strokeWidth="1" opacity="0.6" />
    </svg>
  )
}

export { LogoMark }
