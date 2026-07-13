import { defineConfig, devices } from '@playwright/test'

const releaseBPort = process.env.RELEASE_B_PORT || '3307'
const releaseBBaseUrl = `http://127.0.0.1:${releaseBPort}`
const releaseBDistDir = process.env.NEXT_DIST_DIR || '.next-release-b'

process.env.RELEASE_B_BASE_URL = releaseBBaseUrl

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  workers: 1,
  outputDir: '.playwright-release-b',
  reporter: 'line',
  use: {
    baseURL: releaseBBaseUrl,
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'node scripts/start-release-b-candidate.mjs',
    url: releaseBBaseUrl,
    env: {
      NEXT_DIST_DIR: releaseBDistDir,
      RELEASE_B_PORT: releaseBPort,
    },
    reuseExistingServer: false,
    timeout: 300_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
