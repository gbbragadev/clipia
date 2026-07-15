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

  await page.route('**/api/v1/jobs/job-editor/composition', (route) => {
    const physicalMedia = ['/test-media-0.png', '/test-media-1.png', '/test-media-2.png']
    const currentOrder = savedComposition.sceneOrder ?? [0, 1, 2]
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: 'job-editor',
        script: {
          title: 'Editor avançado',
          scenes: savedComposition.scenes ?? scenes,
          narration: 'Cena A Cena B Cena C',
        },
        words: [
          { word: 'Cena', start: 0, end: 0.4 },
          { word: 'A', start: 0.4, end: 0.8 },
          { word: 'Cena', start: 0.8, end: 1.2 },
          { word: 'B', start: 1.2, end: 1.6 },
        ],
        audio_url: '/test-narration.wav',
        media_urls: currentOrder.map((index) => physicalMedia[index]),
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
    })
  })

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
  const cspErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().includes('Content Security Policy')) {
      cspErrors.push(message.text())
    }
  })
  await installEditorHarness(page)

  await page.goto('/editor/job-editor')

  await expect(page.getByRole('img', { name: /filmstrip da cena 1/i }).first()).toBeVisible()
  await expect(page.getByRole('img', { name: /waveform da narração/i })).toBeVisible()
  await expect(page.locator('[data-waveform-state]')).toHaveAttribute(
    'data-waveform-state',
    /ready|unavailable/,
  )
  await page.waitForTimeout(250)
  expect(cspErrors).toEqual([])
})

test('desktop zooms, reorders, autosaves and undoes one scene move', async ({ page }) => {
  const harness = await installEditorHarness(page)

  await page.goto('/editor/job-editor')

  const timeline = page.locator('[data-timeline-zoom]')
  await expect(page.getByRole('button', { name: 'Aumentar zoom' })).toBeVisible()
  await expect(timeline).toHaveAttribute('data-timeline-zoom', '1')
  await page.getByRole('button', { name: 'Aumentar zoom' }).click()
  await expect(timeline).toHaveAttribute('data-timeline-zoom', '1.5')
  await page.getByRole('button', { name: 'Ajustar timeline' }).click()
  await expect(timeline).toHaveAttribute('data-timeline-zoom', '1')

  await page.getByRole('button', { name: 'Mover cena 3 para trás' }).click()
  await expect.poll(() => harness.getSavedComposition().sceneOrder).toEqual([0, 2, 1])
  await expect(page.getByText(/narração desatualizada/i)).toBeVisible()

  await page.getByRole('button', { name: 'Desfazer' }).click()
  await expect.poll(() => harness.getSavedComposition().sceneOrder).toEqual([0, 1, 2])

  await page.locator('[data-scene-index="0"]').dragTo(
    page.locator('[data-scene-index="2"]'),
  )
  await expect.poll(() => harness.getSavedComposition().sceneOrder).toEqual([1, 2, 0])
  await page.getByRole('button', { name: 'Desfazer' }).click()
  await expect.poll(() => harness.getSavedComposition().sceneOrder).toEqual([0, 1, 2])

  await page.reload()
  await expect(page.getByRole('button', { name: 'Mover cena 3 para trás' })).toBeVisible()
  await expect(page.getByText('Cena A').first()).toBeVisible()
})

for (const width of [320, 390, 393]) {
  test(`mobile ${width}px keeps timeline actions accessible without document overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    const harness = await installEditorHarness(page)

    await page.goto('/editor/job-editor')
    await page.getByRole('button', { name: 'Abrir linha do tempo' }).click()

    const dialog = page.getByRole('dialog', { name: 'Linha do tempo' })
    await expect(dialog).toBeVisible()
    const moveButton = dialog.getByRole('button', { name: 'Mover cena 2 para trás' })
    await expect(moveButton).toHaveCSS('min-height', '44px')
    for (const name of ['Fechar', 'Desfazer', 'Refazer', 'Diminuir zoom', 'Ajustar timeline', 'Aumentar zoom', 'Reproduzir', 'Recolher painel']) {
      const target = dialog.getByRole('button', { name })
      const box = await target.boundingBox()
      expect(box?.height, `${name} precisa de alvo de toque de 44px`).toBeGreaterThanOrEqual(44)
    }
    await moveButton.click()
    await expect.poll(() => harness.getSavedComposition().sceneOrder).toEqual([1, 0, 2])
    await expect(dialog.getByRole('img', { name: /waveform da narração/i })).toBeVisible()

    const viewportMetrics = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(viewportMetrics.scrollWidth).toBe(viewportMetrics.clientWidth)
  })
}
