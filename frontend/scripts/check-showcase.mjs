// Valida que todo video do manifesto existe em public/ e nao ha mp4 orfao sem entrada.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const showcaseDir = path.join(root, 'public', 'showcase')
const manifest = JSON.parse(fs.readFileSync(path.join(showcaseDir, 'showcase.json'), 'utf8'))

let errors = 0
const nicheIds = new Set(manifest.niches.map((n) => n.id))

for (const v of manifest.videos) {
  const file = path.join(root, 'public', v.video.replace(/^\//, ''))
  if (!fs.existsSync(file)) { console.error(`MISSING FILE: ${v.video} (id=${v.id})`); errors++ }
  if (!nicheIds.has(v.niche)) { console.error(`UNKNOWN NICHE: ${v.niche} (id=${v.id})`); errors++ }
}

const referenced = new Set(manifest.videos.map((v) => path.basename(v.video)))
for (const f of fs.readdirSync(showcaseDir).filter((f) => f.endsWith('.mp4'))) {
  if (!referenced.has(f)) { console.error(`ORPHAN MP4 (sem entrada no manifesto): ${f}`); errors++ }
}

if (errors) { console.error(`\n${errors} problema(s).`); process.exit(1) }
console.log(`OK: ${manifest.videos.length} videos, ${manifest.niches.length} nichos, tudo em sincronia.`)
