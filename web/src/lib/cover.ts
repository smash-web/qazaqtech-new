import { asCategory, asMedia, type ArticleDoc } from './types'

/** Цвета автообложек по брендбуку: фон Ink, графика Sky, метка Gold */
export const COVER_THEME = { ink: '#081839', sky: '#1881FF', gold: '#FFC72C', paper: '#F5F7FA' } // цвета нового логотипа

/** Новый логотип (белая версия для тёмного фона) как data URL — для сгенерированных картинок (обложки, Instagram) */
export async function brandLogo(siteUrl: string): Promise<string | null> {
  try {
    const r = await fetch(`${siteUrl}/brand/logo-dark.png`, { cache: 'force-cache' })
    if (!r.ok) return null
    return `data:image/png;base64,${Buffer.from(await r.arrayBuffer()).toString('base64')}`
  } catch {
    return null
  }
}
export const LOGO_RATIO = 444 / 120

/** Обложка статьи: загруженное фото, иначе сгенерированная обложка */
export function coverOf(article: ArticleDoc, size: 'card' | 'hero' | 'og' = 'card') {
  const img = asMedia(article.coverImage)
  const uploaded = img?.sizes?.[size]?.url || img?.url
  if (uploaded) return { src: uploaded, alt: img?.alt || '', generated: false, credit: img?.credit || null }
  const v = Date.parse(article.updatedAt) || 0
  return { src: `/cover/${article.slug}?v=${v}-b3`, alt: article.title, generated: true, credit: null }
}

export const categorySlug = (a: ArticleDoc) => asCategory(a.category)?.slug || ''
