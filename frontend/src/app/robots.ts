import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/dashboard/', '/editor/', '/api/', '/auth/verify', '/auth/reset-password'],
    },
    sitemap: 'https://clipia.com.br/sitemap.xml',
  }
}
