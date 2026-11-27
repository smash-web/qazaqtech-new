import type { MetadataRoute } from 'next'
import { categories, pages, publishedSlugs } from '@/lib/cms'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [docs, cats, pgs] = await Promise.all([publishedSlugs(), categories(), pages()])
  const latest = docs[0]?.updatedAt
  return [
    { url: SITE.url, lastModified: latest, changeFrequency: 'hourly', priority: 1 },
    { url: `${SITE.url}/zhanalyq`, lastModified: latest, changeFrequency: 'hourly', priority: 0.8 },
    ...cats.map((c) => ({ url: `${SITE.url}/sanat/${c.slug}`, lastModified: latest, changeFrequency: 'hourly' as const, priority: 0.7 })),
    ...pgs.map((p) => ({ url: `${SITE.url}/aqparat/${p.slug}`, changeFrequency: 'monthly' as const, priority: 0.3 })),
    ...docs.map((d) => ({ url: `${SITE.url}/zhanalyq/${d.slug}`, lastModified: d.updatedAt, priority: 0.8 })),
  ]
}
