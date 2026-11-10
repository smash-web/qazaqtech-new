import 'server-only'
import { cache } from 'react'
import { unstable_cache } from 'next/cache'
import config from '@payload-config'
import { getPayload, type Where } from 'payload'
import type { ArticleDoc, CategoryDoc } from './types'

/** Теги кэша; сбрасываются хуками коллекций при публикации/изменении */
export const TAGS = { articles: 'articles', categories: 'categories' } as const
const TTL = 600

export const getCMS = cache(() => getPayload({ config }))

// Local API работает с overrideAccess: true, поэтому фильтр «опубликовано» задаём явно
const published: Where = { status: { equals: 'published' } }

type ListArgs = { page?: number; limit?: number; category?: string | number; exclude?: (string | number)[] }

export const latestArticles = unstable_cache(
  async ({ page = 1, limit = 20, category, exclude }: ListArgs = {}) => {
    const payload = await getCMS()
    const and: Where[] = [published]
    if (category !== undefined) and.push({ category: { equals: category } })
    if (exclude?.length) and.push({ id: { not_in: exclude } })
    const res = await payload.find({
      collection: 'articles', where: { and }, sort: '-publishedAt', page, limit, depth: 1,
      select: { content: false },
    })
    return { docs: res.docs as unknown as ArticleDoc[], totalPages: res.totalPages, page: res.page ?? page }
  },
  ['latestArticles'],
  { tags: [TAGS.articles], revalidate: TTL },
)

export const articleBySlug = cache(
  unstable_cache(
    async (slug: string) => {
      const payload = await getCMS()
      const res = await payload.find({
        collection: 'articles', where: { and: [published, { slug: { equals: slug } }] }, limit: 1, depth: 1,
      })
      return (res.docs[0] as unknown as ArticleDoc) || null
    },
    ['articleBySlug'],
    { tags: [TAGS.articles], revalidate: TTL },
  ),
)

export const categories = cache(
  unstable_cache(
    async () => {
      const payload = await getCMS()
      const res = await payload.find({ collection: 'categories', sort: 'order', limit: 50, depth: 0 })
      return res.docs as unknown as CategoryDoc[]
    },
    ['categories'],
    { tags: [TAGS.categories], revalidate: 3600 },
  ),
)

export const categoryBySlug = async (slug: string) => (await categories()).find((c) => c.slug === slug) || null

export const publishedSlugs = unstable_cache(
  async () => {
    const payload = await getCMS()
    const res = await payload.find({
      collection: 'articles', where: published, sort: '-publishedAt', limit: 5000, depth: 0,
      select: { slug: true, updatedAt: true },
    })
    return res.docs as unknown as { slug: string; updatedAt: string }[]
  },
  ['publishedSlugs'],
  { tags: [TAGS.articles], revalidate: 3600 },
)

/** Поиск не кэшируем. Для больших объёмов — заменить на Meilisearch/Typesense */
export async function searchArticles(q: string, page = 1) {
  const payload = await getCMS()
  const res = await payload.find({
    collection: 'articles',
    where: { and: [published, { or: [{ title: { like: q } }, { excerpt: { like: q } }] }] },
    sort: '-publishedAt', page, limit: 20, depth: 1, select: { content: false },
  })
  return { docs: res.docs as unknown as ArticleDoc[], totalPages: res.totalPages }
}
