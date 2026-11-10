import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { ArticleCard } from '@/components/ArticleCard'
import { Pagination } from '@/components/Pagination'
import { categoryBySlug, latestArticles } from '@/lib/cms'

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<{ page?: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const cat = await categoryBySlug((await params).slug)
  return cat ? { title: cat.name, description: cat.description || undefined, alternates: { canonical: `/sanat/${cat.slug}` } } : {}
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const cat = await categoryBySlug((await params).slug)
  if (!cat) notFound()
  const page = Math.max(1, Number((await searchParams).page) || 1)
  const res = await latestArticles({ category: cat.id, page, limit: 24 })
  return (
    <>
      <h1 className="section-title">{cat.name}</h1>
      {cat.description && <p className="lead">{cat.description}</p>}
      {res.docs.length ? (
        <section className="grid">{res.docs.map((a) => <ArticleCard key={a.id} article={a} />)}</section>
      ) : (
        <p className="empty">Бұл айдарда әзірге жаңалық жоқ.</p>
      )}
      <Pagination page={page} totalPages={res.totalPages} basePath={`/sanat/${cat.slug}`} />
    </>
  )
}
