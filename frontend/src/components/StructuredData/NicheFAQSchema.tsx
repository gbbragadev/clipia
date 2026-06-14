import type { NicheContent } from '@/lib/niches'
import { JsonLd } from './JsonLd'

// Emite schema.org/FAQPage a partir das FAQs do nicho — habilita rich snippets de FAQ no Google.
export function NicheFAQSchema({ niche }: { niche: NicheContent }) {
  return (
    <JsonLd
      data={{
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: niche.faqs.map((faq) => ({
          '@type': 'Question',
          name: faq.question,
          acceptedAnswer: { '@type': 'Answer', text: faq.answer },
        })),
      }}
    />
  )
}
