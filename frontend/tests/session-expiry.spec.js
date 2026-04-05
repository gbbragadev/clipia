import { expect, test } from '@playwright/test'

test.skip(true, 'Pending a dedicated auth bootstrap harness for Next dashboard routes.')

test('session expiry redirects to login', async ({ page }) => {
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
      body: '[]',
    })
  })

  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/dashboard$/)
  await page.getByText('Criar novo vídeo').waitFor()
  await page.waitForTimeout(250)

  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('clipia:session-expired'))
  })

  await expect(page).toHaveURL(/\/auth\/login$/)
})
