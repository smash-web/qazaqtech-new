import type { Metadata } from 'next'
import { ArticleCard } from '@/components/ArticleCard'
import { Pagination } from '@/components/Pagination'
import { latestArticles } from '@/lib/cms'

export const metadata: Metadata = { title: 'Барлық жаңалықтар', alternates: { canonical: '/zhanalyq' } }

export default async function Archive({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const page = Math.max(1, Number((await searchParams).page) || 1)
  const res = await latestArticles({ page, limit: 24 })
  return (
    <>
      <h1 className="section-title">Барлық жаңалықтар</h1>
      <section className="grid">{res.docs.map((a) => <ArticleCard key={a.id} article={a} />)}</section>
      <Pagination page={page} totalPages={res.totalPages} basePath="/zhanalyq" />
    </>
  )
}
