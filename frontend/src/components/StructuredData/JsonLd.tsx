// Renderiza um bloco JSON-LD seguro. O conteudo e dado estatico nosso (niches.ts), mas
// escapamos "<" para "<" para garantir que um eventual "</script>" no texto nunca
// quebre nem injete a tag (padrao recomendado para JSON-LD inline).
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data).replace(/</g, '\\u003c')
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />
}
