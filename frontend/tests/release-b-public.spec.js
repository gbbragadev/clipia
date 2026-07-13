import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'
import { CTA_LABEL, NAV_LINKS } from '../src/components/landing/lib/data'
import { getArticleLinkProps } from '../src/lib/markdown-links'
import { loadShowcase, SHOWCASE_CATALOG } from '../src/lib/showcase'

const frontendRoot = process.cwd()
const appBaseUrl = process.env.RELEASE_B_BASE_URL || 'http://127.0.0.1:3307'
const apex = 'https://clipia.com.br'
const postSlug = 'como-criar-videos-com-ia-gratis'

test('links de artigo distinguem mesma origem, externos e protocol-relative', () => {
  expect(getArticleLinkProps('/blog')).toEqual({})
  expect(getArticleLinkProps('https://clipia.com.br/criar/curiosidades')).toEqual({})
  expect(getArticleLinkProps('https://example.com/referencia')).toEqual({
    target: '_blank',
    rel: 'noopener noreferrer',
  })
  expect(getArticleLinkProps('//example.com/referencia')).toEqual({
    target: '_blank',
    rel: 'noopener noreferrer',
  })
})

test('catalogo da landing usa o manifesto runtime e recua ao canonico quando inseguro', async () => {
  const originalFetch = globalThis.fetch
  const runtimeCatalog = {
    niches: [{ id: 'runtime', label: 'Runtime', icon: 'sparkles' }],
    videos: [],
  }

  try {
    let requestedUrl = ''
    globalThis.fetch = async (input) => {
      requestedUrl = String(input)
      return new Response(JSON.stringify(runtimeCatalog), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }

    await expect(loadShowcase()).resolves.toEqual(runtimeCatalog)
    expect(requestedUrl).toBe('/showcase/showcase.json')

    globalThis.fetch = async () => new Response('indisponivel', { status: 503 })
    await expect(loadShowcase()).resolves.toEqual(SHOWCASE_CATALOG)

    globalThis.fetch = async () =>
      new Response(JSON.stringify({ niches: [], videos: 'invalido' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    await expect(loadShowcase()).resolves.toEqual(SHOWCASE_CATALOG)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('artigos usam Markdown GFM sem HTML cru e protegem links absolutos', async ({ page }) => {
  await page.goto(`${appBaseUrl}/blog/${postSlug}`)

  const article = page.locator('article .prose')
  await expect(article.locator('ol')).toHaveCount(1)
  await expect(article.locator('ol > li')).toHaveCount(3)
  await expect(article).not.toContainText('**')

  const absoluteLink = article.locator('a[href="https://clipia.com.br/criar/curiosidades"]').first()
  await expect(absoluteLink).not.toHaveAttribute('target', '_blank')
  await expect(absoluteLink).not.toHaveAttribute('rel', /noopener|noreferrer/)

  const source = fs.readFileSync(
    path.join(frontendRoot, 'src', 'app', 'blog', '[slug]', 'page.tsx'),
    'utf8',
  )
  expect(source).toContain('ReactMarkdown')
  expect(source).toContain('remarkGfm')
  expect(source).toContain('getArticleLinkProps')
  expect(source).not.toContain('isomorphic-dompurify')
  expect(source).not.toContain('dangerouslySetInnerHTML')
})

test('rotas indexaveis publicam canonical apex e metadados especificos', async ({ page }) => {
  test.setTimeout(120_000)
  const routes = [
    '/',
    '/exemplos',
    '/blog',
    `/blog/${postSlug}`,
    '/criar/curiosidades',
    '/suporte',
    '/termos',
    '/privacidade',
    '/v/ocean',
  ]

  for (const route of routes) {
    await page.goto(`${appBaseUrl}${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      'href',
      `${apex}${route === '/' ? '' : route}`,
    )
  }

  const legalMetadata = [
    ['/suporte', /Suporte/, /ajuda|suporte/i],
    ['/termos', /Termos de Uso/, /termos|regras/i],
    ['/privacidade', /Pol[ií]tica de Privacidade/, /privacidade|dados/i],
  ]

  for (const [route, title, description] of legalMetadata) {
    await page.goto(`${appBaseUrl}${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveTitle(title)
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', description)
  }
})

test('datas de artigo coincidem na pagina, schema e sitemap', async ({ page, request }) => {
  await page.goto(`${appBaseUrl}/blog/${postSlug}`)
  await expect(page.locator('article time')).toHaveAttribute('datetime', '2026-04-05')

  const schemas = await page.locator('script[type="application/ld+json"]').allTextContents()
  const blogSchema = schemas.map((value) => JSON.parse(value)).find((value) => value['@type'] === 'BlogPosting')
  expect(blogSchema?.datePublished).toBe('2026-04-05')

  const sitemap = await (await request.get(`${appBaseUrl}/sitemap.xml`)).text()
  expect(sitemap).toContain(`<loc>${apex}/blog/${postSlug}</loc>`)
  expect(sitemap).toContain('<lastmod>2026-04-05</lastmod>')
  expect(sitemap).toContain(`<loc>${apex}/suporte</loc>`)
  expect(sitemap).toContain(`<loc>${apex}/termos</loc>`)
  expect(sitemap).toContain(`<loc>${apex}/privacidade</loc>`)
  expect(sitemap).not.toContain('www.clipia.com.br')
})

test('www redireciona permanentemente para apex preservando rota e query', async ({ request }) => {
  const response = await request.get(`${appBaseUrl}/blog?origem=www`, {
    headers: { host: 'www.clipia.com.br' },
    maxRedirects: 0,
  })

  expect(response.status()).toBe(308)
  expect(response.headers().location).toBe(`${apex}/blog?origem=www`)
})

test('landing cabe em 320, 390 e 393 px sem mascarar overflow global', async ({ page }) => {
  const globalCss = fs.readFileSync(path.join(frontendRoot, 'src', 'app', 'globals.css'), 'utf8')
  expect(globalCss).not.toMatch(/body\s*\{[^}]*overflow-x\s*:\s*hidden/s)

  for (const width of [320, 390, 393]) {
    await page.setViewportSize({ width, height: 420 })
    await page.goto(`${appBaseUrl}/`)

    await page.getByRole('button', { name: 'Abrir menu' }).click()
    const menu = page.locator('#menu-mobile')
    await expect(menu).toBeVisible()
    await expect(menu).toHaveCSS('overflow-y', 'auto')

    const menuLinks = [
      ...NAV_LINKS.map((link) => link.label),
      CTA_LABEL,
      'Entrar',
    ]
    await expect(menu.getByRole('link')).toHaveCount(menuLinks.length)

    for (const label of menuLinks) {
      const link = menu.getByRole('link', { name: label, exact: true })
      await link.evaluate((element) => {
        const scrollContainer = element.closest('#menu-mobile')
        if (!scrollContainer) return
        const linkRect = element.getBoundingClientRect()
        const menuRect = scrollContainer.getBoundingClientRect()
        scrollContainer.scrollTop += linkRect.top - menuRect.top
      })
      await expect(link).toBeVisible()
      await expect
        .poll(
          () =>
            link.evaluate((element) => {
              const linkRect = element.getBoundingClientRect()
              const menuRect = document.querySelector('#menu-mobile')?.getBoundingClientRect()
              return Boolean(
                menuRect &&
                linkRect.top >= menuRect.top - 1 &&
                linkRect.bottom <= menuRect.bottom + 1,
              )
            }),
          { message: `${label} inacessivel em ${width}px` },
        )
        .toBe(true)
    }

    const menuMetrics = await menu.evaluate((element) => {
      const rect = element.getBoundingClientRect()
      return {
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        top: rect.top,
        viewportHeight: window.innerHeight,
      }
    })
    expect(menuMetrics.clientHeight).toBeLessThanOrEqual(
      menuMetrics.viewportHeight - menuMetrics.top + 1,
    )
    expect(menuMetrics.scrollHeight).toBeGreaterThan(menuMetrics.clientHeight)

    await page.getByRole('button', { name: 'Fechar menu' }).click()
    await page.setViewportSize({ width, height: 900 })

    const fan = page.getByRole('group', { name: 'Exemplos de videos em celulares' })
    await fan.scrollIntoViewIfNeeded()
    const box = await fan.boundingBox()
    expect(box, `showcase fan ausente em ${width}px`).not.toBeNull()
    expect(box.x, `showcase fan inicia fora da viewport em ${width}px`).toBeGreaterThanOrEqual(-1)
    expect(box.x + box.width, `showcase fan termina fora da viewport em ${width}px`).toBeLessThanOrEqual(width + 1)

    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(dimensions.content, `overflow horizontal em ${width}px`).toBeLessThanOrEqual(dimensions.viewport)
  }
})

test('todas as rotas de autenticacao bloqueiam indexacao e seguimento', async ({ page }) => {
  const authRoutes = [
    '/auth/login',
    '/auth/register',
    '/auth/forgot-password',
    '/auth/reset-password?email=qa%40clipia.com.br',
    '/auth/verify?email=qa%40clipia.com.br',
  ]

  for (const route of authRoutes) {
    await page.goto(`${appBaseUrl}${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('meta[name="robots"]'), route).toHaveAttribute(
      'content',
      /noindex, nofollow/,
    )
  }
})

test('catalogo canonico mostra videos do nicho e fallback quando vazio no HTML inicial', async ({ request }) => {
  const withVideos = await (await request.get(`${appBaseUrl}/criar/curiosidades`)).text()
  expect(withVideos).toContain('/v/ocean')

  const withoutVideos = await (await request.get(`${appBaseUrl}/criar/historias`)).text()
  expect(withoutVideos).toContain('Ver todos os exemplos')
  expect(withoutVideos).not.toContain('data-niche-video-grid')
})

test('recuperacao de senha exibe Enviar codigo com acento', async ({ page }) => {
  await page.goto(`${appBaseUrl}/auth/forgot-password`)
  await expect(page.getByRole('button', { name: 'Enviar código', exact: true })).toBeVisible()
})
