import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: 'https://clipia.com.br', lastModified: new Date(), changeFrequency: 'weekly', priority: 1 },
    { url: 'https://clipia.com.br/auth/login', lastModified: new Date(), changeFrequency: 'monthly', priority: 0.5 },
    { url: 'https://clipia.com.br/auth/register', lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
  ]
}
