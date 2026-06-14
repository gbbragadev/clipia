// Renderiza o icone do logo ClipIA (mark, sem texto -> sem dependencia de fonte)
// para app/assets/outro/logo.png usando sharp (ja instalado no frontend).
import sharp from 'sharp'
import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(here, '../../app/assets/outro/logo.png')

const SVG = `<svg width="360" height="360" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#8b5cf6"/><stop offset="50%" stop-color="#7c3aed"/><stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
    <linearGradient id="s" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#c4b5fd"/><stop offset="100%" stop-color="#93c5fd"/>
    </linearGradient>
  </defs>
  <rect x="3" y="3" width="34" height="34" rx="8" fill="url(#g)"/>
  <rect x="6" y="9" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="6" y="18" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="6" y="27" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="31" y="9" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="31" y="18" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="31" y="27" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <polygon points="16,12 16,28 28,20" fill="white" opacity="0.95"/>
  <circle cx="32" cy="8" r="3" fill="url(#s)" opacity="0.9"/>
  <line x1="32" y1="4" x2="32" y2="12" stroke="white" stroke-width="1" opacity="0.6"/>
  <line x1="28" y1="8" x2="36" y2="8" stroke="white" stroke-width="1" opacity="0.6"/>
</svg>`

await mkdir(dirname(OUT), { recursive: true })
await sharp(Buffer.from(SVG)).png().toFile(OUT)
console.log('logo ->', OUT)
