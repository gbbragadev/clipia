// Valida que o vocabulario de nichos esta sincronizado entre niches.ts (manifesto SEO)
// e showcase.json (videos). Erros: niche usado sem definicao no manifesto. Avisos: nicho
// definido sem nenhum video ainda (esperado ate a biblioteca crescer).
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const nichesTs = fs.readFileSync(path.join(root, 'src', 'lib', 'niches.ts'), 'utf8')
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'public', 'showcase', 'showcase.json'), 'utf8'))

// Extrai os slugs das entradas do array NICHES (valores string literais `slug: '...'`).
const slugs = new Set([...nichesTs.matchAll(/slug:\s*'([^']+)'/g)].map((m) => m[1]))
if (slugs.size === 0) {
  console.error('ERRO: nenhum slug encontrado em niches.ts (regex falhou?)')
  process.exit(1)
}

let errors = 0
const usedNiches = new Set()

for (const v of manifest.videos) {
  usedNiches.add(v.niche)
  if (!slugs.has(v.niche)) {
    console.error(`ERRO: video id=${v.id} usa niche "${v.niche}" que nao existe em niches.ts`)
    errors++
  }
}

for (const n of manifest.niches) {
  if (!slugs.has(n.id)) {
    console.error(`ERRO: showcase.json declara niche "${n.id}" que nao existe em niches.ts`)
    errors++
  }
}

const empty = [...slugs].filter((s) => !usedNiches.has(s))
if (empty.length) {
  console.warn(`AVISO: ${empty.length} nicho(s) sem video ainda: ${empty.join(', ')}`)
}

if (errors) {
  console.error(`\n${errors} problema(s) de sincronia niches.ts <-> showcase.json.`)
  process.exit(1)
}
console.log(`OK: ${slugs.size} nichos em niches.ts, ${usedNiches.size} com video, tudo em sincronia.`)
