import { latestArticles } from '@/lib/cms'
import { coverOf } from '@/lib/cover'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** Карта для Google News: только статьи за последние 2 суток (требование Google), до 1000 штук */
export async function GET() {
  const since = Date.now() - 48 * 3600 * 1000
  const { docs } = await latestArticles({ limit: 200 })
  const fresh = docs.filter((a) => new Date(a.publishedAt || a.updatedAt).getTime() >= since)
  const urls = fresh.map((a) => {
    const img = new URL(coverOf(a, 'og').src, SITE.url).toString()
    return `
  <url>
    <loc>${SITE.url}/zhanalyq/${a.slug}</loc>
    <news:news>
      <news:publication><news:name>${esc(SITE.name)}</news:name><news:language>kk</news:language></news:publication>
      <news:publication_date>${new Date(a.publishedAt || a.updatedAt).toISOString()}</news:publication_date>
      <news:title>${esc(a.title)}</news:title>
    </news:news>
    <image:image><image:loc>${esc(img)}</image:loc></image:image>
  </url>`
  }).join('')
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">${urls}
</urlset>`
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=600' } })
}
