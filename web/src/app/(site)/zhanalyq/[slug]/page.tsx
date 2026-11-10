import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { RichText } from '@payloadcms/richtext-lexical/react'
import { ArticleCard } from '@/components/ArticleCard'
import { articleBySlug, latestArticles } from '@/lib/cms'
import { formatDate, SITE } from '@/lib/site'
import { asCategory, asMedia } from '@/lib/types'


type Props = { params: Promise<{ slug: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const a = await articleBySlug((await params).slug)
  if (!a) return {}
  const img = asMedia(a.coverImage)
  const description = a.meta?.description || a.excerpt || undefined
  return {
    title: a.meta?.title || a.title,
    description,
    alternates: { canonical: `/zhanalyq/${a.slug}` },
    openGraph: {
      type: 'article', title: a.title, description, publishedTime: a.publishedAt || undefined,
      images: img?.sizes?.og?.url ? [img.sizes.og.url] : undefined,
    },
  }
}

export default async function ArticlePage({ params }: Props) {
  const article = await articleBySlug((await params).slug)
  if (!article) notFound()
  const cat = asCategory(article.category)
  const img = asMedia(article.coverImage)
  const related = cat ? (await latestArticles({ category: cat.id, limit: 4, exclude: [article.id] })).docs : []

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'NewsArticle',
    headline: article.title,
    description: article.excerpt,
    inLanguage: 'kk',
    datePublished: article.publishedAt,
    dateModified: article.updatedAt,
    mainEntityOfPage: `${SITE.url}/zhanalyq/${article.slug}`,
    image: img?.url ? [img.url] : undefined,
    publisher: { '@type': 'Organization', name: SITE.name },
    isBasedOn: article.sources?.map((s) => s.url),
  }

  return (
    <article className="article">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, '\\u003c') }} />
      <div className="meta">
        {cat && <Link href={`/sanat/${cat.slug}`} className="tag">{cat.name}</Link>}
        <time dateTime={article.publishedAt || undefined}>{formatDate(article.publishedAt)}</time>
      </div>
      <h1 className="article__title">{article.title}</h1>
      {article.excerpt && <p className="article__lead">{article.excerpt}</p>}
      {img?.url && (
        <figure className="article__cover">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img.sizes?.hero?.url || img.url} alt={img.alt || ''} />
          {img.credit && <figcaption>{img.credit}</figcaption>}
        </figure>
      )}
      <div className="prose">
        <RichText data={article.content as never} />
      </div>

      {!!article.sources?.length && (
        <aside className="sources">
          <h2>Дереккөздер</h2>
          <ul>
            {article.sources.map((s) => (
              <li key={s.url}><a href={s.url} target="_blank" rel="noopener nofollow">{s.name}</a></li>
            ))}
          </ul>
        </aside>
      )}
      {article.aiGenerated && (
        <p className="ai-note">Бұл материал жасанды интеллект көмегімен аталған дереккөздер негізінде дайындалды.</p>
      )}
      {!!article.tags?.length && (
        <p className="tags">{article.tags.map((t) => <span key={t.tag} className="tag tag--muted">#{t.tag}</span>)}</p>
      )}
      {!!related.length && (
        <section>
          <h2 className="section-title">Ұқсас жаңалықтар</h2>
          <div className="grid">{related.map((a) => <ArticleCard key={a.id} article={a} />)}</div>
        </section>
      )}
    </article>
  )
}
