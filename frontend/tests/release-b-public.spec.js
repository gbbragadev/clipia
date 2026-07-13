import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'
import { CTA_LABEL, NAV_LINKS } from '../src/components/landing/lib/data'
import { blogPosts } from '../src/lib/blog-posts'
import { getArticleLinkProps } from '../src/lib/markdown-links'
import { NICHES } from '../src/lib/niches'
import { loadShowcase, SHOWCASE_CATALOG } from '../src/lib/showcase'

const frontendRoot = process.cwd()
const appBaseUrl = process.env.RELEASE_B_BASE_URL || 'http://127.0.0.1:3307'
const apex = 'https://clipia.com.br'
const postSlug = blogPosts[0].slug
const checkoutUrl = 'https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=qa'
const firstPurchaseId = '00000000-0000-4000-8000-000000000001'
const secondPurchaseId = '00000000-0000-4000-8000-000000000002'
const dispatchId = '00000000-0000-4000-8000-000000000101'
const checkoutAttemptStorageKey = 'clipia_checkout_attempt'

const STATIC_INDEXABLE_ROUTES = ['/', '/exemplos', '/blog', '/suporte', '/termos', '/privacidade']
const NICHE_ROUTES = NICHES.map((niche) => `/criar/${niche.slug}`)
const BLOG_ROUTES = blogPosts.map((post) => `/blog/${post.slug}`)
const VIEWER_ROUTES = SHOWCASE_CATALOG.videos.map((video) => `/v/${video.id}`)
const INDEXABLE_ROUTES = [
  ...STATIC_INDEXABLE_ROUTES,
  ...NICHE_ROUTES,
  ...BLOG_ROUTES,
  ...VIEWER_ROUTES,
]
const AUTH_ROUTE_SPECS = [
  { path: '/auth/login', visit: '/auth/login' },
  { path: '/auth/register', visit: '/auth/register' },
  { path: '/auth/forgot-password', visit: '/auth/forgot-password' },
  {
    path: '/auth/reset-password',
    visit: '/auth/reset-password?email=qa%40clipia.com.br',
  },
  { path: '/auth/verify', visit: '/auth/verify?email=qa%40clipia.com.br' },
]
const PUBLIC_ROUTE_SPECS = [
  ...INDEXABLE_ROUTES.map((route) => ({ path: route, visit: route, indexable: true })),
  ...AUTH_ROUTE_SPECS.map((route) => ({ ...route, indexable: false })),
]
const ROUTE_MATRIX_VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 320, height: 844 },
  { width: 390, height: 844 },
  { width: 393, height: 844 },
]

async function mockCreditsPage(page, { selectedPackage = 'starter' } = {}) {
  await page.addInitScript(() => {
    localStorage.setItem('clipia_token', 'qa-token')
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'qa-checkout-user',
        email: 'qa-checkout@clipia.com.br',
        name: 'QA Checkout',
        credits: 2,
        plan: 'free',
        email_verified: true,
        referral_code: 'QA-CHECKOUT',
        selected_package: selectedPackage === 'pro' ? 'professional' : selectedPackage,
      }),
    }),
  )
  await page.route('**/api/v1/credits/packages', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'starter',
          name: 'Starter',
          credits: 12,
          price_brl: 1990,
          price_display: 'R$ 19,90',
          bonus_percent: 20,
          bonus_credits: 2,
        },
        {
          id: 'popular',
          name: 'Popular',
          credits: 36,
          price_brl: 4990,
          price_display: 'R$ 49,90',
          bonus_percent: 20,
          bonus_credits: 6,
        },
        {
          id: 'professional',
          selected_package: 'professional',
          name: 'Profissional',
          credits: 100,
          base_credits: 100,
          price_brl: 12990,
          price_display: 'R$ 129,90',
          bonus_percent: 20,
          bonus_credits: 20,
          total_credits: 120,
        },
      ]),
    }),
  )
  await page.route('**/api/v1/credits/history', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ purchases: [] }),
    }),
  )
  await page.route('https://www.mercadopago.com.br/checkout/**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Checkout QA</title>' }),
  )
}

async function openCreditsPage(page, selectedPackage = 'starter') {
  await page.goto(`${appBaseUrl}/dashboard/credits?selected_package=${selectedPackage}`)
  await expect(
    page.getByRole('button', {
      name: `Continuar com ${selectedPackage === 'starter' ? 'Starter' : selectedPackage === 'popular' ? 'Popular' : 'Profissional'}`,
    }),
  ).toBeVisible()
}

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

test('todos os artigos usam Markdown GFM sem HTML cru e protegem links externos', async ({ page }) => {
  for (const post of blogPosts) {
    await page.goto(`${appBaseUrl}/blog/${post.slug}`)
    const article = page.locator('article .prose')
    await expect(article).not.toContainText('**')
    await expect(article.locator('script, iframe, object, embed, style')).toHaveCount(0)

    const links = await article.locator('a').evaluateAll((elements) =>
      elements.map((element) => ({
        href: element.getAttribute('href'),
        target: element.getAttribute('target'),
        rel: element.getAttribute('rel'),
      })),
    )
    for (const link of links) {
      if (!link.href) continue
      const destination = new URL(link.href, 'https://clipia.com.br')
      if (destination.origin === 'https://clipia.com.br') {
        expect(link.target, `${post.slug}: link interno abriu nova aba`).not.toBe('_blank')
      } else {
        expect(link.target, `${post.slug}: link externo sem nova aba`).toBe('_blank')
        expect(link.rel, `${post.slug}: link externo sem protecao`).toBe('noopener noreferrer')
      }
    }
  }

  await page.goto(`${appBaseUrl}/blog/${postSlug}`)
  const firstArticle = page.locator('article .prose')
  await expect(firstArticle.locator('ol')).toHaveCount(1)
  await expect(firstArticle.locator('ol > li')).toHaveCount(3)

  const absoluteLink = firstArticle.locator('a[href="https://clipia.com.br/criar/curiosidades"]').first()
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

test('as 24 rotas indexaveis publicam um canonical apex autorreferente', async ({ page }) => {
  test.setTimeout(180_000)
  expect(INDEXABLE_ROUTES).toHaveLength(24)
  expect(new Set(INDEXABLE_ROUTES).size).toBe(24)

  for (const route of INDEXABLE_ROUTES) {
    await page.goto(`${appBaseUrl}${route}`, { waitUntil: 'domcontentloaded' })
    const canonical = page.locator('link[rel="canonical"]')
    await expect(canonical, route).toHaveCount(1)
    await expect(canonical, route).toHaveAttribute('href', `${apex}${route === '/' ? '' : route}`)
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
  for (const route of VIEWER_ROUTES) {
    expect(sitemap).toContain(`<loc>${apex}${route}</loc>`)
  }
  expect(sitemap).not.toContain('www.clipia.com.br')
})

test('www redireciona estatico, dinamico, auth e viewer preservando rota e query', async ({ request }) => {
  const routes = [
    '/suporte?origem=www',
    '/criar/curiosidades?utm_source=qa',
    '/auth/register?selected_package=starter',
    '/v/ocean?ref=share',
  ]
  for (const route of routes) {
    const response = await request.get(`${appBaseUrl}${route}`, {
      headers: { host: 'www.clipia.com.br' },
      maxRedirects: 0,
    })
    expect(response.status(), route).toBe(308)
    expect(response.headers().location, route).toBe(`${apex}${route}`)
  }
})

test('matriz real cobre 29 rotas em desktop e 320/390/393 sem erro ou overflow', async ({ browser }) => {
  test.setTimeout(600_000)
  expect(PUBLIC_ROUTE_SPECS).toHaveLength(29)
  expect(new Set(PUBLIC_ROUTE_SPECS.map((route) => route.path)).size).toBe(29)
  expect(PUBLIC_ROUTE_SPECS.length * ROUTE_MATRIX_VIEWPORTS.length).toBe(116)

  for (const viewport of ROUTE_MATRIX_VIEWPORTS) {
    for (const route of PUBLIC_ROUTE_SPECS) {
      const page = await browser.newPage({ viewport })
      const consoleErrors = []
      const pageErrors = []
      page.on('console', (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text())
      })
      page.on('pageerror', (error) => pageErrors.push(error.message))
      await page.route('**/api/v1/config', (requestRoute) =>
        requestRoute.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ welcome_credit_bonus: 2, purchase_bonus_percent: 20 }),
        }),
      )

      const label = `${route.path} em ${viewport.width}x${viewport.height}`
      try {
        const response = await page.goto(`${appBaseUrl}${route.visit}`, {
          waitUntil: 'domcontentloaded',
        })
        expect(response, `${label}: navegacao sem resposta`).not.toBeNull()
        expect(response.status(), `${label}: status HTTP`).toBe(200)
        await page.waitForLoadState('load')
        await expect
          .poll(async () => (await page.locator('body').innerText()).trim().length, {
            message: `${label}: pagina sem conteudo utilizavel apos hidratacao`,
            timeout: 5_000,
          })
          .toBeGreaterThan(20)

        const bodyText = (await page.locator('body').innerText()).trim()
        expect(bodyText, `${label}: erro do Next`).not.toMatch(
          /Application error|This page could not be found|Internal Server Error/i,
        )

        const dimensions = await page.evaluate(() => {
          const documentElement = document.documentElement
          const body = document.body
          const viewportWidth = documentElement.clientWidth
          const escapedContainers = [...document.querySelectorAll('main, header, footer, form, article')]
            .filter((element) => {
              const style = window.getComputedStyle(element)
              const rect = element.getBoundingClientRect()
              return (
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                rect.width > 0 &&
                (rect.left < -1 || rect.right > viewportWidth + 1)
              )
            })
            .map((element) => ({
              tag: element.tagName.toLowerCase(),
              className: element.getAttribute('class') || '',
              rect: element.getBoundingClientRect().toJSON(),
            }))
          return {
            viewportWidth,
            documentWidth: documentElement.scrollWidth,
            bodyWidth: body.scrollWidth,
            escapedContainers,
          }
        })
        expect(dimensions.documentWidth, `${label}: overflow no documento`).toBeLessThanOrEqual(
          dimensions.viewportWidth + 1,
        )
        expect(dimensions.bodyWidth, `${label}: overflow no body`).toBeLessThanOrEqual(
          dimensions.viewportWidth + 1,
        )
        expect(dimensions.escapedContainers, `${label}: container fora da viewport`).toEqual([])

        if (route.indexable) {
          const canonical = page.locator('link[rel="canonical"]')
          await expect(canonical, label).toHaveCount(1)
          await expect(canonical, label).toHaveAttribute(
            'href',
            `${apex}${route.path === '/' ? '' : route.path}`,
          )
        } else {
          await expect(page.locator('meta[name="robots"]'), label).toHaveAttribute(
            'content',
            /noindex, nofollow/,
          )
        }

        expect(consoleErrors, `${label}: console.error`).toEqual([])
        expect(pageErrors, `${label}: pageerror`).toEqual([])
      } finally {
        await page.close()
      }
    }
  }
})

test('landing cabe em 320, 390 e 393 px sem mascarar overflow global', async ({ page }) => {
  const globalCss = fs.readFileSync(path.join(frontendRoot, 'src', 'app', 'globals.css'), 'utf8')
  expect(globalCss).not.toMatch(/body\s*\{[^}]*overflow-x\s*:\s*hidden/s)

  for (const width of [320, 390, 393]) {
    await page.setViewportSize({ width, height: 420 })
    await page.goto(`${appBaseUrl}/`)

    await page.getByRole('button', { name: 'Abrir menu' }).click()
    const menu = page.locator('#menu-mobile')
    await expect(menu).toHaveCount(1)
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
    await expect(page.getByRole('button', { name: 'Abrir menu' })).toBeVisible()
    await expect(menu).toHaveCSS('max-height', '0px')
    await expect(menu).toHaveCSS('opacity', '0')
    await page.setViewportSize({ width, height: 900 })

    const fan = page.getByRole('group', { name: 'Exemplos de videos em celulares' })
    await fan.scrollIntoViewIfNeeded()
    const box = await fan.boundingBox()
    expect(box, `showcase fan ausente em ${width}px`).not.toBeNull()
    expect(box.x, `showcase fan inicia fora da viewport em ${width}px`).toBeGreaterThanOrEqual(-1)
    expect(box.x + box.width, `showcase fan termina fora da viewport em ${width}px`).toBeLessThanOrEqual(width + 1)

    const dimensions = await page.evaluate(() => {
      const viewport = document.documentElement.clientWidth
      const offenders = [...document.querySelectorAll('*')]
        .map((element) => {
          const rect = element.getBoundingClientRect()
          return {
            element: `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}`,
            className: typeof element.className === 'string' ? element.className.slice(0, 180) : '',
            parentClassName:
              typeof element.parentElement?.className === 'string'
                ? element.parentElement.className.slice(0, 180)
                : '',
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          }
        })
        .filter(({ right, width: elementWidth }) => elementWidth > 0 && right > viewport + 1)
        .sort((a, b) => a.right - b.right)
        .slice(0, 12)
      return {
        viewport,
        innerWidth: window.innerWidth,
        bodyClientWidth: document.body.clientWidth,
        bodyScrollWidth: document.body.scrollWidth,
        content: document.documentElement.scrollWidth,
        offenders,
      }
    })
    expect(
      dimensions.content,
      `overflow horizontal em ${width}px; metricas=${JSON.stringify(dimensions)}`,
    ).toBeLessThanOrEqual(dimensions.viewport)

    // Force a document boundary between viewport cases so a closing menu
    // transition from the previous width cannot overlap the next hydration.
    await page.goto('about:blank')
  }
})

test('todas as rotas de autenticacao bloqueiam indexacao e seguimento', async ({ page }) => {
  expect(AUTH_ROUTE_SPECS).toHaveLength(5)
  for (const route of AUTH_ROUTE_SPECS) {
    await page.goto(`${appBaseUrl}${route.visit}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('meta[name="robots"]'), route.path).toHaveAttribute(
      'content',
      /noindex, nofollow/,
    )
  }
})

test('os sete nichos usam somente exemplos canonicos ou exibem fallback sem grade vazia', async ({ page }) => {
  expect(NICHES).toHaveLength(7)
  for (const niche of NICHES) {
    const expectedVideos = SHOWCASE_CATALOG.videos.filter((video) => video.niche === niche.slug)
    await page.goto(`${appBaseUrl}/criar/${niche.slug}`)
    const grid = page.locator('[data-niche-video-grid]')
    if (expectedVideos.length === 0) {
      await expect(grid, niche.slug).toHaveCount(0)
      await expect(page.getByRole('link', { name: 'Ver todos os exemplos', exact: true }), niche.slug).toBeVisible()
      continue
    }

    const hrefs = await grid.locator('a[href^="/v/"]').evaluateAll((links) =>
      links.map((link) => link.getAttribute('href')),
    )
    expect(hrefs, niche.slug).toEqual(expectedVideos.map((video) => `/v/${video.id}`))
  }
})

test('recuperacao de senha exibe Enviar codigo com acento', async ({ page }) => {
  await page.goto(`${appBaseUrl}/auth/forgot-password`)
  await expect(page.getByRole('button', { name: 'Enviar código', exact: true })).toBeVisible()
})

test('landing carrega headlines uma vez e preserva atribuicao nos CTAs de pacote', async ({ page }) => {
  let headlineLoads = 0
  await page.route('**/ab/headlines.json', async (route) => {
    headlineLoads += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    })
  })

  await page.goto(
    `${appBaseUrl}/?utm_source=google&utm_medium=cpc&utm_campaign=criadores-faceless&utm_content=video-a&utm_term=faceless&utm_id=ads-42`,
  )

  await expect(
    page.getByText(
      'Comece com 2 créditos grátis — até 2 vídeos com voz padrão. Sem cartão.',
      { exact: true },
    ).first(),
  ).toBeVisible()
  await expect(page.getByText('Pix e cartão', { exact: true }).first()).toBeVisible()
  await expect
    .poll(() =>
      page.evaluate(() =>
        ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id'].map(
          (key) => localStorage.getItem(`clipia_${key}`),
        ),
      ),
    )
    .toEqual(['google', 'cpc', 'criadores-faceless', 'video-a', 'faceless', 'ads-42'])

  const packages = [
    ['Escolher Starter', 'starter'],
    ['Escolher Popular', 'popular'],
    ['Escolher Profissional', 'professional'],
  ]

  for (const [label, selectedPackage] of packages) {
    const link = page.getByRole('link', { name: label, exact: true })
    await expect(link).toBeVisible()
    await expect
      .poll(async () => new URL((await link.getAttribute('href')) || '', appBaseUrl).searchParams.toString())
      .toContain(`selected_package=${selectedPackage}`)

    const url = new URL((await link.getAttribute('href')) || '', appBaseUrl)
    expect(url.pathname).toBe('/auth/register')
    expect(url.searchParams.get('selected_package')).toBe(selectedPackage)
    expect(url.searchParams.get('utm_source')).toBe('google')
    expect(url.searchParams.get('utm_medium')).toBe('cpc')
    expect(url.searchParams.get('utm_campaign')).toBe('criadores-faceless')
    expect(url.searchParams.get('utm_content')).toBe('video-a')
    expect(url.searchParams.get('utm_term')).toBe('faceless')
    expect(url.searchParams.get('utm_id')).toBe('ads-42')
    expect(url.searchParams.get('placement')).toBe(`pricing-${selectedPackage}`)
  }

  await expect.poll(() => headlineLoads).toBe(1)
})

test('cadastro e verificacao mantem pacote valido ate a selecao anterior ao checkout', async ({ page }) => {
  let verified = false
  let registerPayload
  let checkoutPayload
  let checkoutCalls = 0

  await page.route('**/api/v1/config', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ welcome_credit_bonus: 2, purchase_bonus_percent: 20 }),
    }),
  )
  await page.route('**/api/v1/auth/register', async (route) => {
    registerPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'qa-token', token_type: 'bearer' }),
    })
  })
  await page.route('**/api/v1/auth/verify-email', async (route) => {
    verified = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'verified', credits: 2 }),
    })
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'qa-user',
        email: 'qa-package@clipia.com.br',
        name: 'QA Package',
        credits: verified ? 2 : 0,
        plan: 'free',
        email_verified: verified,
        referral_code: 'QA-PACKAGE',
        selected_package: 'professional',
      }),
    }),
  )
  await page.route('**/api/v1/credits/packages', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'starter',
          name: 'Starter',
          credits: 10,
          price_brl: 1990,
          price_display: 'R$ 19,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
        {
          id: 'popular',
          name: 'Popular',
          credits: 30,
          price_brl: 4990,
          price_display: 'R$ 49,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
        {
          id: 'pro',
          name: 'Profissional',
          credits: 100,
          price_brl: 12990,
          price_display: 'R$ 129,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
      ]),
    }),
  )
  await page.route('**/api/v1/credits/history', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ purchases: [] }),
    }),
  )
  await page.route('**/api/v1/credits/checkout', async (route) => {
    checkoutCalls += 1
    checkoutPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ checkout_url: checkoutUrl, purchase_id: firstPurchaseId }),
    })
  })
  await page.route('https://www.mercadopago.com.br/checkout/**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Checkout QA</title>' }),
  )

  await page.goto(
    `${appBaseUrl}/auth/register?selected_package=professional&utm_source=google&utm_medium=cpc&utm_campaign=criadores-faceless&utm_content=register-content&utm_term=register-term&utm_id=register-id`,
  )
  await page.locator('#name').fill('QA Package')
  await page.locator('#email').fill('qa-package@clipia.com.br')
  await page.locator('#password').fill('SenhaQa123!')
  await page.locator('input[type="checkbox"]').check()
  await page.locator('form button[type="submit"]').click()

  await expect(page).toHaveURL(/\/auth\/verify\?/)
  expect(registerPayload).toMatchObject({
    selected_package: 'professional',
    utm_source: 'google',
    utm_medium: 'cpc',
    utm_campaign: 'criadores-faceless',
  })
  expect(registerPayload).not.toHaveProperty('utm_content')
  expect(registerPayload).not.toHaveProperty('utm_term')
  expect(registerPayload).not.toHaveProperty('utm_id')
  expect(
    await page.evaluate(() =>
      ['utm_content', 'utm_term', 'utm_id'].map((key) =>
        localStorage.getItem(`clipia_${key}`),
      ),
    ),
  ).toEqual([null, null, null])
  expect(new URL(page.url()).searchParams.get('selected_package')).toBe('professional')

  const otp = page.locator('input[inputmode="numeric"]')
  for (const [index, digit] of [...'123456'].entries()) {
    await otp.nth(index).fill(digit)
  }
  await page.locator('form button[type="submit"]').click()

  await expect(page).toHaveURL(/\/dashboard\/credits\?selected_package=professional$/)
  const professional = page.locator('[data-package-id="pro"]')
  await expect(professional).toHaveAttribute('aria-current', 'true')
  await expect(professional).toContainText('Pacote preselecionado')
  expect(checkoutCalls).toBe(0)

  await page.getByRole('button', { name: 'Escolher Starter', exact: true }).click()
  await expect(page.locator('[data-package-id="starter"]')).toHaveAttribute('aria-current', 'true')
  await expect(professional).not.toHaveAttribute('aria-current', 'true')
  expect(checkoutCalls).toBe(0)

  await page.getByRole('button', { name: 'Continuar com Starter', exact: true }).click()
  await expect.poll(() => checkoutCalls).toBe(1)
  expect(checkoutPayload).toMatchObject({ package: 'starter', provider: 'mercadopago' })
})

test('cadastro ignora selected_package desconhecido', async ({ page }) => {
  let registerPayload

  await page.route('**/api/v1/config', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ welcome_credit_bonus: 2, purchase_bonus_percent: 0 }),
    }),
  )
  await page.route('**/api/v1/auth/register', async (route) => {
    registerPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'qa-token', token_type: 'bearer' }),
    })
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'qa-user',
        email: 'qa-invalid@clipia.com.br',
        name: 'QA Invalid',
        credits: 0,
        plan: 'free',
        email_verified: false,
        referral_code: 'QA-INVALID',
      }),
    }),
  )

  await page.goto(`${appBaseUrl}/auth/register?selected_package=enterprise`)
  await page.locator('#name').fill('QA Invalid')
  await page.locator('#email').fill('qa-invalid@clipia.com.br')
  await page.locator('#password').fill('SenhaQa123!')
  await page.locator('input[type="checkbox"]').check()
  await page.locator('form button[type="submit"]').click()

  await expect(page).toHaveURL(/\/auth\/verify\?/)
  expect(registerPayload).not.toHaveProperty('selected_package')
  expect(new URL(page.url()).searchParams.has('selected_package')).toBe(false)
})

test('verificacao sem query retoma pacote persistido no usuario sem checkout automatico', async ({ page }) => {
  let verified = false
  let checkoutCalls = 0

  await page.addInitScript(() => {
    localStorage.setItem('clipia_token', 'qa-token')
  })
  await page.route('**/api/v1/auth/verify-email', async (route) => {
    verified = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'verified', credits: 2 }),
    })
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'qa-user',
        email: 'qa-otp-fallback@clipia.com.br',
        name: 'QA OTP Fallback',
        credits: verified ? 2 : 0,
        plan: 'free',
        email_verified: verified,
        referral_code: 'QA-OTP-FALLBACK',
        selected_package: 'professional',
      }),
    }),
  )
  await page.route('**/api/v1/credits/packages', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'pro',
          name: 'Profissional',
          credits: 100,
          price_brl: 12990,
          price_display: 'R$ 129,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
      ]),
    }),
  )
  await page.route('**/api/v1/credits/history', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ purchases: [] }),
    }),
  )
  await page.route('**/api/v1/credits/checkout', (route) => {
    checkoutCalls += 1
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ checkout_url: checkoutUrl, purchase_id: firstPurchaseId }),
    })
  })

  await page.goto(`${appBaseUrl}/auth/verify?email=qa-otp-fallback%40clipia.com.br`)
  const otp = page.locator('input[inputmode="numeric"]')
  for (const [index, digit] of [...'654321'].entries()) {
    await otp.nth(index).fill(digit)
  }
  await page.locator('form button[type="submit"]').click()

  await expect(page).toHaveURL(/\/dashboard\/credits\?selected_package=professional$/)
  await expect(page.locator('[data-package-id="pro"]')).toHaveAttribute(
    'aria-current',
    'true',
  )
  expect(checkoutCalls).toBe(0)
})

test('creditos usa pacote persistido no usuario quando a query se perde', async ({ page }) => {
  let checkoutCalls = 0

  await page.addInitScript(() => {
    localStorage.setItem('clipia_token', 'qa-token')
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'qa-user',
        email: 'qa-fallback@clipia.com.br',
        name: 'QA Fallback',
        credits: 2,
        plan: 'free',
        email_verified: true,
        referral_code: 'QA-FALLBACK',
        selected_package: 'professional',
      }),
    }),
  )
  await page.route('**/api/v1/credits/packages', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'starter',
          name: 'Starter',
          credits: 10,
          price_brl: 1990,
          price_display: 'R$ 19,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
        {
          id: 'popular',
          name: 'Popular',
          credits: 30,
          price_brl: 4990,
          price_display: 'R$ 49,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
        {
          id: 'pro',
          name: 'Pro',
          credits: 100,
          price_brl: 12990,
          price_display: 'R$ 129,90',
          bonus_percent: 0,
          bonus_credits: 0,
        },
      ]),
    }),
  )
  await page.route('**/api/v1/credits/history', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ purchases: [] }),
    }),
  )
  await page.route('**/api/v1/credits/checkout', (route) => {
    checkoutCalls += 1
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ checkout_url: checkoutUrl, purchase_id: firstPurchaseId }),
    })
  })

  await page.goto(`${appBaseUrl}/dashboard/credits`)

  const professional = page.locator('[data-package-id="pro"]')
  await expect(professional).toHaveAttribute('aria-current', 'true')
  await expect(professional).toContainText('Pacote preselecionado')
  await expect(page.getByRole('button', { name: 'Continuar com Profissional' })).toBeVisible()
  expect(checkoutCalls).toBe(0)

  await page.goto(`${appBaseUrl}/dashboard/credits?selected_package=popular`)
  await expect(page.locator('[data-package-id="popular"]')).toHaveAttribute('aria-current', 'true')
  await expect(professional).not.toHaveAttribute('aria-current', 'true')
  expect(checkoutCalls).toBe(0)
})

test('selecionar pacote nunca cria checkout automaticamente', async ({ page }) => {
  let checkoutCalls = 0
  await mockCreditsPage(page)
  await page.route('**/api/v1/credits/checkout', (route) => {
    checkoutCalls += 1
    return route.fulfill({ status: 500, body: 'nao deveria chamar' })
  })

  await openCreditsPage(page)
  expect(checkoutCalls).toBe(0)

  await page.getByRole('button', { name: 'Escolher Popular', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continuar com Popular', exact: true })).toBeVisible()
  expect(checkoutCalls).toBe(0)
})

test('reutiliza Idempotency-Key depois de perder a primeira resposta', async ({ page }) => {
  const keys = []
  let checkoutCalls = 0
  await mockCreditsPage(page)
  await page.route('**/api/v1/credits/checkout', async (route) => {
    checkoutCalls += 1
    keys.push(route.request().headers()['idempotency-key'])
    if (checkoutCalls === 1) return route.abort('connectionfailed')
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ checkout_url: checkoutUrl, purchase_id: firstPurchaseId }),
    })
  })

  await openCreditsPage(page)
  const continueButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
  await continueButton.click()
  await expect.poll(() => checkoutCalls).toBe(1)
  await expect(continueButton).toBeEnabled()
  await expect(page).toHaveURL(/\/dashboard\/credits/)

  await continueButton.click()
  await expect(page).toHaveURL(checkoutUrl)
  expect(keys).toHaveLength(2)
  expect(keys[0]).toMatch(/^[0-9a-f]{8}-[0-9a-f-]{27}$/i)
  expect(keys[1]).toBe(keys[0])
})

test('202 consulta pending ate ready sem navegar antes da URL segura', async ({ page }) => {
  let checkoutCalls = 0
  let statusCalls = 0
  await mockCreditsPage(page)
  await page.route(`**/api/v1/credits/checkout/${firstPurchaseId}`, (route) => {
    statusCalls += 1
    const ready = statusCalls >= 2
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        purchase_id: firstPurchaseId,
        dispatch_id: dispatchId,
        state: ready ? 'ready' : 'pending',
        ...(ready ? { checkout_url: checkoutUrl } : {}),
      }),
    })
  })
  await page.route('**/api/v1/credits/checkout', (route) => {
    checkoutCalls += 1
    return route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        purchase_id: firstPurchaseId,
        dispatch_id: dispatchId,
        state: 'pending',
      }),
    })
  })

  await openCreditsPage(page)
  await page.getByRole('button', { name: 'Continuar com Starter', exact: true }).click()
  await expect.poll(() => statusCalls).toBe(1)
  await expect(page).toHaveURL(/\/dashboard\/credits/)
  await expect(page).toHaveURL(checkoutUrl)
  expect(checkoutCalls).toBe(1)
  expect(statusCalls).toBe(2)
})

for (const terminalState of ['failed', 'cancelled']) {
  test(`${terminalState} limpa tentativa e reabilita checkout sem redirecionar`, async ({ page }) => {
    let checkoutCalls = 0
    await mockCreditsPage(page)
    await page.route(`**/api/v1/credits/checkout/${firstPurchaseId}`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          purchase_id: firstPurchaseId,
          dispatch_id: dispatchId,
          state: terminalState,
        }),
      }),
    )
    await page.route('**/api/v1/credits/checkout', (route) => {
      checkoutCalls += 1
      return route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          purchase_id: firstPurchaseId,
          dispatch_id: dispatchId,
          state: 'pending',
        }),
      })
    })

    await openCreditsPage(page)
    const continueButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
    await continueButton.click()
    await expect(continueButton).toBeEnabled()
    await expect(page).toHaveURL(/\/dashboard\/credits/)
    expect(checkoutCalls).toBe(1)
    expect(await page.evaluate((key) => sessionStorage.getItem(key), checkoutAttemptStorageKey)).toBeNull()
  })
}

test('409 descarta chave, reabilita botao e nao redireciona', async ({ page }) => {
  const keys = []
  await mockCreditsPage(page)
  await page.route('**/api/v1/credits/checkout', (route) => {
    keys.push(route.request().headers()['idempotency-key'])
    return route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'idempotency_key_conflict' }),
    })
  })

  await openCreditsPage(page)
  const continueButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
  await continueButton.click()
  await expect(continueButton).toBeEnabled()
  await expect(page).toHaveURL(/\/dashboard\/credits/)
  expect(await page.evaluate((key) => sessionStorage.getItem(key), checkoutAttemptStorageKey)).toBeNull()

  await continueButton.click()
  await expect.poll(() => keys.length).toBe(2)
  expect(keys[0]).toBeTruthy()
  expect(keys[1]).not.toBe(keys[0])
})

test('reload com purchase_id consulta status antes de qualquer novo POST', async ({ page }) => {
  let checkoutCalls = 0
  let statusCalls = 0
  let afterReload = false
  await mockCreditsPage(page)
  await page.route(`**/api/v1/credits/checkout/${firstPurchaseId}`, (route) => {
    statusCalls += 1
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        purchase_id: firstPurchaseId,
        dispatch_id: dispatchId,
        state: afterReload ? 'ready' : 'pending',
        ...(afterReload ? { checkout_url: checkoutUrl } : {}),
      }),
    })
  })
  await page.route('**/api/v1/credits/checkout', (route) => {
    checkoutCalls += 1
    return route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        purchase_id: firstPurchaseId,
        dispatch_id: dispatchId,
        state: 'pending',
      }),
    })
  })

  await openCreditsPage(page)
  await page.getByRole('button', { name: 'Continuar com Starter', exact: true }).click()
  await expect.poll(() => statusCalls).toBeGreaterThan(0)
  await page.reload()
  afterReload = true

  const continueButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
  await expect(continueButton).toBeVisible()
  await continueButton.click()
  await expect(page).toHaveURL(checkoutUrl)
  expect(checkoutCalls).toBe(1)
})

test('polling esgotado preserva tentativa e informa que checkout segue preparando', async ({ page }) => {
  test.setTimeout(20_000)
  await mockCreditsPage(page)
  await page.route(`**/api/v1/credits/checkout/${firstPurchaseId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        purchase_id: firstPurchaseId,
        dispatch_id: dispatchId,
        state: 'pending',
      }),
    }),
  )
  await page.route('**/api/v1/credits/checkout', (route) =>
    route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        purchase_id: firstPurchaseId,
        dispatch_id: dispatchId,
        state: 'pending',
      }),
    }),
  )

  await openCreditsPage(page)
  const continueButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
  await continueButton.click()
  await expect(page.getByText('Checkout ainda em preparação', { exact: true })).toBeVisible()
  await expect(continueButton).toBeEnabled()
  await expect(page).toHaveURL(/\/dashboard\/credits/)
  expect(await page.evaluate((key) => sessionStorage.getItem(key), checkoutAttemptStorageKey)).not.toBeNull()
})

test('trocar provider ou pacote gera fingerprint e chave novos sem compra automatica', async ({ page }) => {
  const attempts = []
  await mockCreditsPage(page)
  await page.route('**/api/v1/credits/checkout', (route) => {
    attempts.push({
      key: route.request().headers()['idempotency-key'],
      body: route.request().postDataJSON(),
    })
    return route.abort('connectionfailed')
  })

  await openCreditsPage(page)
  const starterButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
  await starterButton.click()
  await expect(starterButton).toBeEnabled()

  await page.getByRole('button', { name: 'Escolher Popular', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continuar com Popular', exact: true })).toBeVisible()
  expect(attempts).toHaveLength(1)

  await page.getByRole('button', { name: /^Cartão/ }).click()
  await page.getByRole('button', { name: 'Continuar com Popular', exact: true }).click()
  await expect.poll(() => attempts.length).toBe(2)
  expect(attempts[0].body).toEqual({ package: 'starter', provider: 'mercadopago' })
  expect(attempts[1].body).toEqual({ package: 'popular', provider: 'stripe' })
  expect(attempts[1].key).not.toBe(attempts[0].key)
})

test('resposta de checkout com ID ou URL insegura nunca redireciona', async ({ page }) => {
  let checkoutCalls = 0
  const unsafeResponses = [
    { checkout_url: checkoutUrl, purchase_id: 'nao-e-uuid' },
    {
      checkout_url: 'https://www.mercadopago.com.br.evil.example/checkout',
      purchase_id: firstPurchaseId,
    },
    { checkout_url: 'http://localhost:9999/checkout', purchase_id: secondPurchaseId },
  ]
  await mockCreditsPage(page)
  await page.route('**/api/v1/credits/checkout', (route) => {
    checkoutCalls += 1
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(unsafeResponses[checkoutCalls - 1]),
    })
  })

  await openCreditsPage(page)
  const continueButton = page.getByRole('button', { name: 'Continuar com Starter', exact: true })
  await continueButton.click()
  await expect(continueButton).toBeEnabled()
  await expect(page).toHaveURL(/\/dashboard\/credits/)
  expect(await page.evaluate((key) => sessionStorage.getItem(key), checkoutAttemptStorageKey)).not.toBeNull()

  for (const expectedCalls of [2, 3]) {
    await continueButton.click()
    await expect.poll(() => checkoutCalls).toBe(expectedCalls)
    await expect(continueButton).toBeEnabled()
    await expect(page).toHaveURL(/\/dashboard\/credits/)
  }
})
