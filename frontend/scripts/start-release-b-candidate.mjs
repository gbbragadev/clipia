import { spawn } from 'node:child_process'
import { cpSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const nextBin = require.resolve('next/dist/bin/next')
const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const port = process.env.RELEASE_B_PORT || '3307'
const distDir = process.env.NEXT_DIST_DIR || '.next-release-b'
const distPath = path.resolve(frontendRoot, distDir)
const env = {
  ...process.env,
  NEXT_DIST_DIR: distDir,
  NEXT_TELEMETRY_DISABLED: '1',
}

let activeChild
let stopping = false

function runNode(entrypoint, args, label, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [entrypoint, ...args], {
      cwd: options.cwd || frontendRoot,
      env: options.env || env,
      stdio: 'inherit',
    })
    activeChild = child
    child.once('error', reject)
    child.once('exit', (code, signal) => {
      activeChild = undefined
      if (stopping || code === 0) return resolve()
      reject(new Error(`${label} encerrou com ${signal || `codigo ${code}`}`))
    })
  })
}

function stop() {
  if (stopping) return
  stopping = true
  if (activeChild && !activeChild.killed) activeChild.kill()
}

process.once('SIGINT', stop)
process.once('SIGTERM', stop)

try {
  await runNode(nextBin, ['build'], 'next build')

  const standaloneDir = path.join(distPath, 'standalone')
  const relativeDistDir = path.relative(frontendRoot, distPath)
  cpSync(path.join(frontendRoot, 'public'), path.join(standaloneDir, 'public'), {
    recursive: true,
  })
  cpSync(path.join(distPath, 'static'), path.join(standaloneDir, relativeDistDir, 'static'), {
    recursive: true,
  })

  await runNode(path.join(standaloneDir, 'server.js'), [], 'servidor standalone', {
    cwd: standaloneDir,
    env: {
      ...env,
      HOSTNAME: '127.0.0.1',
      PORT: port,
    },
  })
} catch (error) {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
}
