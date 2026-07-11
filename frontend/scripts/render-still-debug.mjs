// Debug da matriz E2E: renderiza UM frame da composição com os mesmos props do
// export para inspecionar legendas/overlays sem pagar um render completo.
// Usage: node scripts/render-still-debug.mjs --props <props.json> --frame 90 --out <out.png>
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'

import { bundle } from '@remotion/bundler'
import { renderStill, selectComposition } from '@remotion/renderer'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.join(path.resolve(__dirname, '..'), 'src')

function arg(name, def) {
  const i = process.argv.indexOf(name)
  return i >= 0 ? process.argv[i + 1] : def
}

const inputProps = JSON.parse(fs.readFileSync(arg('--props'), 'utf8'))
const frame = Number(arg('--frame', '90'))
const outPath = arg('--out')

const serveUrl = await bundle({
  entryPoint: path.join(srcDir, 'remotion', 'Root.tsx'),
  webpackOverride: (config) => {
    config.resolve = config.resolve || {}
    config.resolve.alias = { ...(config.resolve.alias || {}), '@': srcDir }
    return config
  },
})
const composition = await selectComposition({ serveUrl, id: 'ShortVideo', inputProps, timeoutInMilliseconds: 120000 })
await renderStill({ composition, serveUrl, output: outPath, frame, inputProps, timeoutInMilliseconds: 120000 })
console.log('STILL_OK', outPath)
