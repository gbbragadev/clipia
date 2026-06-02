// Fase 1 spike: render the Remotion "ShortVideo" composition server-side.
// Usage: node scripts/render-composition.mjs --props <props.json> --out <output.mp4>
//
// Reads inputProps (CompositionData) from --props, bundles the Remotion project
// (resolving the `@` -> src alias), and renders via @remotion/renderer. Emits
// JSONL status lines on stdout so a parent process (Celery worker) can track it.

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { bundle } from '@remotion/bundler'
import { renderMedia, selectComposition } from '@remotion/renderer'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, '..')
const srcDir = path.join(frontendRoot, 'src')

function arg(name, def) {
  const i = process.argv.indexOf(name)
  return i >= 0 ? process.argv[i + 1] : def
}

const log = (o) => console.log(JSON.stringify(o))

const propsPath = arg('--props')
const outPath = arg('--out', path.join(frontendRoot, 'out', 'render.mp4'))
if (!propsPath) {
  console.error('missing --props <file>')
  process.exit(2)
}

const inputProps = JSON.parse(fs.readFileSync(propsPath, 'utf8'))
fs.mkdirSync(path.dirname(outPath), { recursive: true })

try {
  const t0 = Date.now()
  log({ status: 'bundling' })
  const serveUrl = await bundle({
    entryPoint: path.join(srcDir, 'remotion', 'Root.tsx'),
    webpackOverride: (config) => {
      config.resolve = config.resolve || {}
      config.resolve.alias = { ...(config.resolve.alias || {}), '@': srcDir }
      return config
    },
  })
  const t1 = Date.now()
  log({ status: 'bundled', seconds: +((t1 - t0) / 1000).toFixed(1) })

  const composition = await selectComposition({ serveUrl, id: 'ShortVideo', inputProps })
  log({
    status: 'composition',
    durationInFrames: composition.durationInFrames,
    fps: composition.fps,
    width: composition.width,
    height: composition.height,
  })

  let lastPct = -1
  await renderMedia({
    composition,
    serveUrl,
    codec: 'h264',
    outputLocation: outPath,
    inputProps,
    pixelFormat: 'yuv420p',
    crf: 23,
    onProgress: ({ progress }) => {
      const pct = Math.round(progress * 100)
      if (pct !== lastPct && pct % 10 === 0) {
        lastPct = pct
        log({ status: 'rendering', progress: pct })
      }
    },
  })
  const t2 = Date.now()
  log({
    status: 'done',
    bundleSeconds: +((t1 - t0) / 1000).toFixed(1),
    renderSeconds: +((t2 - t1) / 1000).toFixed(1),
    totalSeconds: +((t2 - t0) / 1000).toFixed(1),
    output: outPath,
  })
} catch (err) {
  log({ status: 'error', message: String(err && err.stack ? err.stack : err) })
  process.exit(1)
}
