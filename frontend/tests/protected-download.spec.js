import { expect, test } from '@playwright/test'

test.skip(true, 'Pending a dedicated auth bootstrap harness for Next dashboard routes.')

test('dashboard download sends authorization header', async ({ page }) => {
  const requests = []

  await page.addInitScript(() => {
    window.localStorage.setItem('clipia_token', 'test-token')
  })

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-1',
        email: 'user@example.com',
        name: 'User',
        credits: 5,
        plan: 'free',
        email_verified: true,
      }),
    })
  })
  await page.route('**/api/v1/jobs*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          job_id: '11111111-1111-1111-1111-111111111111',
          topic: 'Tema completo para o download autenticado',
          style: 'educational',
          status: 'completed',
          duration_target: 45,
          created_at: '2026-04-04T12:00:00+00:00',
          download_url: '/api/v1/jobs/11111111-1111-1111-1111-111111111111/download',
        },
      ]),
    })
  })
  await page.route('**/api/v1/jobs/11111111-1111-1111-1111-111111111111/download', async (route) => {
    requests.push(route.request().headers()['authorization'] || '')
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'video/mp4',
        'content-disposition': 'attachment; filename="clipia-test.mp4"',
      },
      body: Buffer.from('video'),
    })
  })

  await page.goto('/dashboard')
  await page.getByText('Criar novo vídeo').waitFor()
  await page.getByRole('button', { name: 'Baixar' }).waitFor()
  await page.getByRole('button', { name: 'Baixar' }).click()

  await expect.poll(() => requests.length).toBe(1)
  await expect.poll(() => requests[0]).toBe('Bearer test-token')
})
