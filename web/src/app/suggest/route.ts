import config from '@payload-config'
import { getPayload } from 'payload'

export const dynamic = 'force-dynamic'

/** Подсказки поиска: GET /suggest?q=… → до 6 статей (сначала совпадения в заголовке, потом в лиде и тегах). */
export async function GET(req: Request) {
  const q = (new URL(req.url).searchParams.get('q') || '').trim().slice(0, 60)
  if (q.length < 2) return Response.json({ items: [] })
  const payload = await getPayload({ config })
  const find = (where: object, limit: number) => payload.find({
    collection: 'articles', sort: '-publishedAt', limit, depth: 1,
    where: { and: [{ status: { equals: 'published' } }, where] } as never,
    select: { title: true, slug: true, category: true, publishedAt: true },
  })
  const byTitle = await find({ title: { like: q } }, 6)
  let docs = byTitle.docs
  if (docs.length < 6) {
    const more = await find({ or: [{ excerpt: { like: q } }, { 'tags.tag': { like: q } }] }, 12)
    const seen = new Set(docs.map((d) => d.id))
    docs = [...docs, ...more.docs.filter((d) => !seen.has(d.id))].slice(0, 6)
  }
  const items = docs.map((d) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const a = d as any
    return {
      title: a.title as string, slug: a.slug as string, publishedAt: a.publishedAt as string | null,
      category: a.category && typeof a.category === 'object' ? (a.category.name as string) : null,
    }
  })
  return Response.json({ items }, { headers: { 'Cache-Control': 'public, max-age=30' } })
}
