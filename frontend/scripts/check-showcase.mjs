// Valida que todo video do manifesto existe no disco e nao ha mp4 orfao em public/showcase.
// Suporta dois locais para o campo `video`:
//   /showcase/<file>.mp4          -> frontend/public/showcase (hero, commitado no git)
//   /storage/showcase/<file>.mp4  -> <repo>/storage/showcase   (galeria, servida pelo backend)
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..') // frontend/
const repoRoot = path.resolve(root, '..') // <repo>
const publicShowcaseDir = path.join(root, 'public', 'showcase')
const storageShowcaseDir = path.join(repoRoot, 'storage', 'showcase')
const manifest = JSON.parse(fs.readFileSync(path.join(publicShowcaseDir, 'showcase.json'), 'utf8'))

let errors = 0
const nicheIds = new Set(manifest.niches.map((n) => n.id))
const operationCase = manifest.operationCase
const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/

if (
  !operationCase ||
  typeof operationCase.label !== 'string' ||
  !operationCase.label.trim() ||
  typeof operationCase.disclaimer !== 'string' ||
  !operationCase.disclaimer.trim() ||
  !isoDatePattern.test(operationCase.periodStart || '') ||
  !isoDatePattern.test(operationCase.periodEnd || '') ||
  operationCase.periodStart > operationCase.periodEnd
) {
  console.error('INVALID OPERATION CASE: identidade, período ISO e aviso são obrigatórios')
  errors++
}

// Resolve o caminho fisico de um campo `video` do manifesto.
function resolveVideoPath(video) {
  if (video.startsWith('/storage/showcase/')) {
    return path.join(storageShowcaseDir, path.basename(video))
  }
  // /showcase/<file> (ou qualquer outro sob public/)
  return path.join(root, 'public', video.replace(/^\//, ''))
}

for (const v of manifest.videos) {
  if (!fs.existsSync(resolveVideoPath(v.video))) {
    console.error(`MISSING FILE: ${v.video} (id=${v.id})`)
    errors++
  }
  if (!nicheIds.has(v.niche)) {
    console.error(`UNKNOWN NICHE: ${v.niche} (id=${v.id})`)
    errors++
  }
}

// Orfaos: so checamos public/showcase (o que vive no git). storage/showcase e gerenciado
// pelo promote_to_showcase.py e pode conter muitos arquivos / nao existir em dev.
const referencedInPublic = new Set(
  manifest.videos.filter((v) => !v.video.startsWith('/storage/showcase/')).map((v) => path.basename(v.video))
)
for (const f of fs.readdirSync(publicShowcaseDir).filter((f) => f.endsWith('.mp4'))) {
  if (!referencedInPublic.has(f)) {
    console.error(`ORPHAN MP4 (sem entrada no manifesto): ${f}`)
    errors++
  }
}

if (errors) {
  console.error(`\n${errors} problema(s).`)
  process.exit(1)
}
const representedNiches = new Set(manifest.videos.map((video) => video.niche))
console.log(
  `OK: ${manifest.videos.length} videos, ${representedNiches.size} nichos representados, tudo em sincronia.`,
)
