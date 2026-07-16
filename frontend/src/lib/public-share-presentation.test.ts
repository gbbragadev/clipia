import assert from 'node:assert/strict'
import test from 'node:test'

async function loadPresentationModule(): Promise<Record<string, unknown>> {
  return import('./public-share-presentation.ts').catch(() => ({})) as Promise<Record<string, unknown>>
}

async function loadJsonLdModule(): Promise<Record<string, unknown>> {
  return import('../components/StructuredData/json-ld.ts').catch(() => ({})) as Promise<Record<string, unknown>>
}

function collectStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(collectStrings)
  if (value && typeof value === 'object') return Object.values(value).flatMap(collectStrings)
  return []
}

test('JSON-LD serialization never emits a literal script closing sequence', async () => {
  const module = await loadJsonLdModule()
  assert.equal(typeof module.serializeJsonLd, 'function')
  const serializeJsonLd = module.serializeJsonLd as (data: Record<string, unknown>) => string
  const title = '</script><script>globalThis.pwned = true</script>'

  const serialized = serializeJsonLd({ title })

  assert.equal(serialized.toLowerCase().includes('</script'), false)
  assert.match(serialized, /\\u003c\/script>/)
  assert.equal(JSON.parse(serialized).title, title)
})

test('dynamic public-share metadata and JSON-LD never contain free-form topic or path data', async () => {
  const module = await loadPresentationModule()
  assert.equal(typeof module.buildShareMetadata, 'function')
  assert.equal(typeof module.buildShareJsonLd, 'function')
  assert.equal(typeof module.getShareDisplayTitle, 'function')
  const buildShareMetadata = module.buildShareMetadata as (input: Record<string, unknown>) => Record<string, unknown>
  const buildShareJsonLd = module.buildShareJsonLd as (input: Record<string, unknown>) => Record<string, unknown>
  const getShareDisplayTitle = module.getShareDisplayTitle as (input: Record<string, unknown>) => string
  const malicious = 'owner@example.com +55 45 99999-0000 C:\\Users\\Alice\\private.mp4 </script><script>alert(1)</script>'
  const input = {
    kind: 'public',
    id: 'public-token',
    title: malicious,
    niche: malicious,
    template: malicious,
    video: malicious,
    published_at: '2026-07-16T12:34:56+00:00',
  }

  const metadata = buildShareMetadata(input)
  const jsonLd = buildShareJsonLd(input)
  const recursiveText = collectStrings({ metadata, jsonLd }).join('\n').toLowerCase()

  for (const forbidden of ['owner@example.com', '99999-0000', 'c:\\users\\alice', '</script', 'alert(1)']) {
    assert.equal(recursiveText.includes(forbidden), false, `leaked ${forbidden}`)
  }
  assert.equal(metadata.title, 'Vídeo publicado com ClipIA')
  assert.equal((metadata.openGraph as { title: string }).title, 'Vídeo publicado com ClipIA')
  assert.equal(((metadata.openGraph as { images: Array<{ alt: string }> }).images[0]).alt, 'Vídeo publicado com ClipIA')
  assert.equal(jsonLd.name, 'Vídeo publicado com ClipIA')
  assert.equal(jsonLd.uploadDate, '2026-07-16T12:34:56+00:00')
  assert.equal(getShareDisplayTitle(input), 'Vídeo publicado com ClipIA')
})

test('curated showcase metadata may preserve its controlled title', async () => {
  const module = await loadPresentationModule()
  assert.equal(typeof module.buildShareMetadata, 'function')
  const buildShareMetadata = module.buildShareMetadata as (input: Record<string, unknown>) => Record<string, unknown>

  const metadata = buildShareMetadata({
    kind: 'showcase',
    id: 'controlled-id',
    title: 'Título editorial controlado',
    niche: 'história',
    template: 'documentary',
    video: '/showcase/controlled.mp4',
  })

  assert.equal(metadata.title, 'Título editorial controlado — feito com ClipIA')
  assert.equal((metadata.openGraph as { title: string }).title, 'Título editorial controlado — feito com ClipIA')
})
