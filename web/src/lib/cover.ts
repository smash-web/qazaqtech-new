import { asCategory, asMedia, type ArticleDoc } from './types'

/** Цвета автообложек по брендбуку: фон Ink, графика Sky, метка Gold */
export const COVER_THEME = { ink: '#0B1B3A', sky: '#00AFCA', gold: '#FFC72C', paper: '#F5F7FA' }

/** Обложка статьи: загруженное фото, иначе сгенерированная обложка */
export function coverOf(article: ArticleDoc, size: 'card' | 'hero' | 'og' = 'card') {
  const img = asMedia(article.coverImage)
  const uploaded = img?.sizes?.[size]?.url || img?.url
  if (uploaded) return { src: uploaded, alt: img?.alt || '', generated: false, credit: img?.credit || null }
  const v = Date.parse(article.updatedAt) || 0
  return { src: `/cover/${article.slug}?v=${v}-b2`, alt: article.title, generated: true, credit: null }
}

export const categorySlug = (a: ArticleDoc) => asCategory(a.category)?.slug || ''
