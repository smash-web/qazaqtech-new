import type { MetadataRoute } from 'next'
import { categories, publishedSlugs } from '@/lib/cms'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const docs = await publishedSlugs()
  const cats = await categories()
  return [
    { url: SITE.url, changeFrequency: 'hourly', priority: 1 },
    ...cats.map((c) => ({ url: `${SITE.url}/sanat/${c.slug}`, changeFrequency: 'hourly' as const, priority: 0.7 })),
    ...docs.map((d) => ({ url: `${SITE.url}/zhanalyq/${d.slug}`, lastModified: d.updatedAt, priority: 0.8 })),
  ]
}
