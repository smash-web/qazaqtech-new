// Упрощённые типы для публичной части. Полные типы: npm run generate:types → src/payload-types.ts
export type MediaDoc = { id: number | string; url?: string | null; alt?: string; credit?: string | null
  sizes?: Record<string, { url?: string | null; width?: number | null; height?: number | null }> }
export type CategoryDoc = { id: number | string; name: string; slug: string; description?: string | null }
export type ArticleDoc = {
  id: number | string
  title: string
  slug: string
  excerpt?: string | null
  content: unknown
  coverImage?: MediaDoc | number | string | null
  category?: CategoryDoc | number | string | null
  tags?: { tag: string }[] | null
  sources?: { name: string; url: string }[] | null
  publishedAt?: string | null
  updatedAt: string
  aiGenerated?: boolean | null
  meta?: { title?: string | null; description?: string | null } | null
}

export const asCategory = (c: ArticleDoc['category']): CategoryDoc | null =>
  c && typeof c === 'object' ? c : null
export const asMedia = (m: ArticleDoc['coverImage']): MediaDoc | null => (m && typeof m === 'object' ? m : null)
