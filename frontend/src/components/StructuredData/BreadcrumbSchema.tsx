import { JsonLd } from './JsonLd'

// Emite schema.org/BreadcrumbList — ajuda o Google a exibir a trilha de navegacao nos resultados.
export function BreadcrumbSchema({ items }: { items: Array<{ name: string; url: string }> }) {
  return (
    <JsonLd
      data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: items.map((item, i) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: item.name,
          item: item.url,
        })),
      }}
    />
  )
}
