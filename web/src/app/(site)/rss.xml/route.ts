import { latestArticles } from '@/lib/cms'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export async function GET() {
  const { docs } = await latestArticles({ limit: 50 })
  const items = docs.map((a) => `
    <item>
      <title>${esc(a.title)}</title>
      <link>${SITE.url}/zhanalyq/${a.slug}</link>
      <guid isPermaLink="true">${SITE.url}/zhanalyq/${a.slug}</guid>
      <pubDate>${new Date(a.publishedAt || a.updatedAt).toUTCString()}</pubDate>
      <description>${esc(a.excerpt || '')}</description>
    </item>`).join('')
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>${esc(SITE.name)}</title><link>${SITE.url}</link><language>kk</language>
  <description>${esc(SITE.tagline)}</description>${items}
</channel></rss>`
  return new Response(xml, { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } })
}
