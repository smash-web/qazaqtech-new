import { asCategory, asMedia, type ArticleDoc } from './types'

/** Цвета рубрик для автообложек: [фон-начало, фон-конец, акцент] */
export const CATEGORY_THEME: Record<string, [string, string, string]> = {
  ai: ['#1e1b4b', '#4338ca', '#a5b4fc'],
  'big-tech': ['#0c1222', '#1d4ed8', '#93c5fd'],
  startups: ['#1a0f2e', '#9333ea', '#e9d5ff'],
  security: ['#1a0b0b', '#b91c1c', '#fecaca'],
  gadgets: ['#04201d', '#0f766e', '#99f6e4'],
  dev: ['#0b1a10', '#15803d', '#bbf7d0'],
  science: ['#0a1628', '#0369a1', '#bae6fd'],
  policy: ['#1c1408', '#b45309', '#fde68a'],
}
export const DEFAULT_THEME: [string, string, string] = ['#0b1220', '#0a66ff', '#bfdbfe']

/** Обложка статьи: загруженное фото, иначе сгенерированная обложка */
export function coverOf(article: ArticleDoc, size: 'card' | 'hero' | 'og' = 'card') {
  const img = asMedia(article.coverImage)
  const uploaded = img?.sizes?.[size]?.url || img?.url
  if (uploaded) return { src: uploaded, alt: img?.alt || '', generated: false, credit: img?.credit || null }
  const v = Date.parse(article.updatedAt) || 0
  return { src: `/cover/${article.slug}?v=${v}`, alt: article.title, generated: true, credit: null }
}

export const categorySlug = (a: ArticleDoc) => asCategory(a.category)?.slug || ''
