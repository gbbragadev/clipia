import { serializeJsonLd } from './json-ld'

// Renderiza JSON-LD seguro mesmo quando algum campo vier de conteudo externo.
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  const json = serializeJsonLd(data)
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />
}
