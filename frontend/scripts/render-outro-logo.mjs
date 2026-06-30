// Renderiza o icone do logo ClipIA (mark, sem texto -> sem dependencia de fonte)
// para app/assets/outro/logo.png usando sharp (ja instalado no frontend).
import sharp from 'sharp'
import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(here, '../../app/assets/outro/logo.png')

// Logo unico ClipIA (identidade coral/grafite) — espelha components/brand/Logo.
// Mark: quadrado grafite arredondado + gradiente coral/azure + play coral + ponto mint.
// Visivel sobre o fundo escuro/borrado do selo de outro.
const SVG = `<svg width="512" height="512" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ff5638" stop-opacity="0.30"/>
      <stop offset="55%" stop-color="#ff5638" stop-opacity="0.05"/>
      <stop offset="100%" stop-color="#3e9bff" stop-opacity="0.20"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="36" height="36" rx="10" fill="#11141d"/>
  <rect x="2" y="2" width="36" height="36" rx="10" fill="url(#g)"/>
  <rect x="2.5" y="2.5" width="35" height="35" rx="9.5" fill="none" stroke="#ffffff" stroke-opacity="0.14" stroke-width="0.6"/>
  <path d="M15 12.5 L28 20 L15 27.5 Z" fill="#ff5638"/>
  <circle cx="29.5" cy="29.5" r="2.6" fill="#43e0ad"/>
</svg>`

await mkdir(dirname(OUT), { recursive: true })
await sharp(Buffer.from(SVG)).png().toFile(OUT)
console.log('logo ->', OUT)
