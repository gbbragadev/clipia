import { expect, test } from '@playwright/test'

function makeSilentWav(durationSeconds = 2, sampleRate = 8000) {
  const sampleCount = durationSeconds * sampleRate
  const dataSize = sampleCount * 2
  const wav = Buffer.alloc(44 + dataSize)
  wav.write('RIFF', 0)
  wav.writeUInt32LE(36 + dataSize, 4)
  wav.write('WAVE', 8)
  wav.write('fmt ', 12)
  wav.writeUInt32LE(16, 16)
  wav.writeUInt16LE(1, 20)
  wav.writeUInt16LE(1, 22)
  wav.writeUInt32LE(sampleRate, 24)
  wav.writeUInt32LE(sampleRate * 2, 28)
  wav.writeUInt16LE(2, 32)
  wav.writeUInt16LE(16, 34)
  wav.write('data', 36)
  wav.writeUInt32LE(dataSize, 40)
  return wav
}

async function installEditorHarness(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('clipia_token', 'editor-test-token')
  })

  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      id: 'user-editor',
      email: 'editor@example.com',
      name: 'Editor QA',
      credits: 20,
      plan: 'pro',
      email_verified: true,
      referral_code: 'EDITORQA',
    }),
  }))

  const scenes = [
    { text: 'Cena A', keywords_en: ['brain'], duration_hint: 2 },
    { text: 'Cena B', keywords_en: ['memory'], duration_hint: 3 },
    { text: 'Cena C', keywords_en: ['neuron'], duration_hint: 5 },
  ]
  let savedComposition = {
    scenes,
    sceneOrder: [0, 1, 2],
    narrationStale: false,
  }

  await page.route('**/api/v1/jobs/job-editor/composition', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      job_id: 'job-editor',
      script: { title: 'Editor avançado', scenes, narration: 'Cena A Cena B Cena C' },
      words: [
        { word: 'Cena', start: 0, end: 0.4 },
        { word: 'A', start: 0.4, end: 0.8 },
        { word: 'Cena', start: 0.8, end: 1.2 },
        { word: 'B', start: 1.2, end: 1.6 },
      ],
      audio_url: '/test-narration.wav',
      media_urls: ['/test-media-0.png', '/test-media-1.png', '/test-media-2.png'],
      subtitle_style: {},
      editor_state: { composition: savedComposition },
      template_id: 'stock_narration',
      layout_type: 'fullscreen',
      fps: 30,
      width: 1080,
      height: 1920,
      pending_credits: 0,
      music_asset_id: null,
      music_volume: 0.12,
    }),
  }))

  await page.route('**/api/v1/jobs/job-editor/edit', async (route) => {
    const body = route.request().postDataJSON()
    savedComposition = structuredClone(body.editor_state.composition)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'saved' }),
    })
  })

  await page.route('**/test-narration.wav', (route) => route.fulfill({
    status: 200,
    contentType: 'audio/wav',
    body: makeSilentWav(),
  }))
  await page.route(/\/test-media-\d+\.png$/, (route) => {
    const index = route.request().url().match(/(\d+)\.png$/)?.[1] ?? '0'
    return route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640"><rect width="100%" height="100%" fill="#1d2433"/><text x="50%" y="50%" fill="#ff5638" font-size="72" text-anchor="middle">${index}</text></svg>`,
    })
  })

  return { getSavedComposition: () => savedComposition }
}

test('desktop exposes filmstrips and a narration waveform', async ({ page }) => {
  await installEditorHarness(page)

  await page.goto('/editor/job-editor')

  await expect(page.getByRole('img', { name: /filmstrip da cena 1/i }).first()).toBeVisible()
  await expect(page.getByRole('img', { name: /waveform da narração/i })).toBeVisible()
  await expect(page.locator('[data-waveform-state]')).toHaveAttribute(
    'data-waveform-state',
    /ready|unavailable/,
  )
})
