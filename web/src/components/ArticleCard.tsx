import Link from 'next/link'
import { formatDate } from '@/lib/site'
import { asCategory, asMedia, type ArticleDoc } from '@/lib/types'

export function ArticleCard({ article, variant = 'default' }: { article: ArticleDoc; variant?: 'default' | 'hero' | 'compact' }) {
  const cat = asCategory(article.category)
  const img = asMedia(article.coverImage)
  const src = img?.sizes?.[variant === 'hero' ? 'hero' : 'card']?.url || img?.url
  return (
    <article className={`card card--${variant}`}>
      {src && variant !== 'compact' && (
        <Link href={`/zhanalyq/${article.slug}`} className="card__media" tabIndex={-1}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={img?.alt || ''} loading={variant === 'hero' ? 'eager' : 'lazy'} />
        </Link>
      )}
      <div className="card__body">
        <div className="meta">
          {cat && <Link href={`/sanat/${cat.slug}`} className="tag">{cat.name}</Link>}
          <time dateTime={article.publishedAt || undefined}>{formatDate(article.publishedAt)}</time>
        </div>
        <h2 className="card__title">
          <Link href={`/zhanalyq/${article.slug}`}>{article.title}</Link>
        </h2>
        {variant !== 'compact' && article.excerpt && <p className="card__excerpt">{article.excerpt}</p>}
      </div>
    </article>
  )
}
