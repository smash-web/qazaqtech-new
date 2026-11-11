import Link from 'next/link'
import { coverOf } from '@/lib/cover'
import { Views } from './Views'
import { formatDate, timeAgo } from '@/lib/site'
import { asCategory, type ArticleDoc } from '@/lib/types'

type Variant = 'default' | 'hero' | 'compact' | 'list'

export function ArticleCard({ article, variant = 'default' }: { article: ArticleDoc; variant?: Variant }) {
  const cat = asCategory(article.category)
  const cover = coverOf(article, variant === 'hero' ? 'hero' : 'card')
  const href = `/zhanalyq/${article.slug}`
  const showImage = variant !== 'compact'
  const showExcerpt = variant === 'default' || variant === 'hero'
  return (
    <article className={`card card--${variant}`}>
      {showImage && (
        <Link href={href} className="card__media" tabIndex={-1} aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={cover.src} alt="" width={1200} height={675} loading={variant === 'hero' ? 'eager' : 'lazy'} />
        </Link>
      )}
      <div className="card__body">
        <div className="meta">
          {cat && variant !== 'list' && <Link href={`/sanat/${cat.slug}`} className="tag">{cat.name}</Link>}
          <time dateTime={article.publishedAt || undefined} title={formatDate(article.publishedAt)}>
            {timeAgo(article.publishedAt)}
          </time>
          <Views id={article.id} initial={article.views ?? 0} />
        </div>
        <h2 className="card__title"><Link href={href}>{article.title}</Link></h2>
        {showExcerpt && article.excerpt && <p className="card__excerpt">{article.excerpt}</p>}
      </div>
    </article>
  )
}
