import type { Metadata } from 'next'
import { ArticleCard } from '@/components/ArticleCard'
import { Pagination } from '@/components/Pagination'
import { TagsPanel } from '@/components/Panels'
import { articlesByTag } from '@/lib/cms'

type Props = { params: Promise<{ tag: string }>; searchParams: Promise<{ page?: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const tag = decodeURIComponent((await params).tag)
  return { title: `#${tag}`, alternates: { canonical: `/teg/${encodeURIComponent(tag)}` } }
}

export default async function TagPage({ params, searchParams }: Props) {
  const tag = decodeURIComponent((await params).tag).slice(0, 60)
  const page = Math.max(1, Number((await searchParams).page) || 1)
  const res = await articlesByTag(tag, page)
  return (
    <>
      <h1 className="section-title">#{tag}</h1>
      {res.docs.length ? (
        <section className="grid">{res.docs.map((a) => <ArticleCard key={a.id} article={a} />)}</section>
      ) : (
        <p className="empty">Бұл тақырып бойынша әзірге жаңалық жоқ.</p>
      )}
      <Pagination page={page} totalPages={res.totalPages} basePath={`/teg/${encodeURIComponent(tag)}`} />
      <div className="panels panels--single"><TagsPanel /></div>
    </>
  )
}
