import 'server-only'
import { cache } from 'react'
import { unstable_cache } from 'next/cache'
import config from '@payload-config'
import { getPayload, type Where } from 'payload'
import type { ArticleDoc, CategoryDoc, PageDoc, SiteSettingsDoc } from './types'

/** Теги кэша; сбрасываются хуками коллекций при публикации/изменении */
export const TAGS = {
  articles: 'articles', categories: 'categories', pages: 'pages', settings: 'settings', sources: 'sources',
} as const
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

// --- Информационные страницы и настройки -------------------------------------------------
export const pages = cache(
  unstable_cache(
    async () => {
      const payload = await getCMS()
      const res = await payload.find({
        collection: 'pages', sort: 'order', limit: 50, depth: 0, select: { title: true, slug: true, showInFooter: true },
      })
      return res.docs as unknown as Pick<PageDoc, 'id' | 'title' | 'slug' | 'showInFooter'>[]
    },
    ['pages'],
    { tags: [TAGS.pages], revalidate: 3600 },
  ),
)

export const pageBySlug = cache(
  unstable_cache(
    async (slug: string) => {
      const payload = await getCMS()
      const res = await payload.find({ collection: 'pages', where: { slug: { equals: slug } }, limit: 1, depth: 0 })
      return (res.docs[0] as unknown as PageDoc) || null
    },
    ['pageBySlug'],
    { tags: [TAGS.pages], revalidate: 3600 },
  ),
)

export const siteSettings = cache(
  unstable_cache(
    async () => {
      const payload = await getCMS()
      return (await payload.findGlobal({ slug: 'site-settings', depth: 0 })) as unknown as SiteSettingsDoc
    },
    ['siteSettings'],
    { tags: [TAGS.settings], revalidate: 3600 },
  ),
)

/** Издания, за которыми следит редакция (для блока «Біз бақылайтын басылымдар») */
export const watchedSources = cache(
  unstable_cache(
    async () => {
      const payload = await getCMS()
      const res = await payload.find({
        collection: 'sources', where: { active: { equals: true } }, sort: '-weight', limit: 100, depth: 0,
        select: { name: true, siteUrl: true },
      })
      const seen = new Set<string>()
      return (res.docs as unknown as { name: string; siteUrl?: string | null }[])
        .map((d) => ({ name: d.name.replace(/:.*$/, '').trim(), siteUrl: d.siteUrl || null }))
        .filter((d) => (seen.has(d.name) ? false : (seen.add(d.name), true)))
    },
    ['watchedSources'],
    { tags: [TAGS.sources], revalidate: 3600 },
  ),
)

/** Популярные теги за последние публикации */
export const popularTags = unstable_cache(
  async (limit = 20) => {
    const payload = await getCMS()
    const res = await payload.find({
      collection: 'articles', where: published, sort: '-publishedAt', limit: 200, depth: 0, select: { tags: true },
    })
    const counts = new Map<string, number>()
    for (const d of res.docs as unknown as { tags?: { tag: string }[] }[])
      for (const t of d.tags || []) counts.set(t.tag, (counts.get(t.tag) || 0) + 1)
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit).map(([tag, count]) => ({ tag, count }))
  },
  ['popularTags'],
  { tags: [TAGS.articles], revalidate: 3600 },
)

/** Статьи по тегу */
export const articlesByTag = unstable_cache(
  async (tag: string, page = 1) => {
    const payload = await getCMS()
    const res = await payload.find({
      collection: 'articles', where: { and: [published, { 'tags.tag': { equals: tag } }] },
      sort: '-publishedAt', page, limit: 24, depth: 1, select: { content: false },
    })
    return { docs: res.docs as unknown as ArticleDoc[], totalPages: res.totalPages }
  },
  ['articlesByTag'],
  { tags: [TAGS.articles], revalidate: TTL },
)
