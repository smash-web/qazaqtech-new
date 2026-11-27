import type { Metadata } from 'next'
import { ArticleCard } from '@/components/ArticleCard'
import { Pagination } from '@/components/Pagination'
import { latestArticles } from '@/lib/cms'

type SP = { searchParams: Promise<{ page?: string }> }

export async function generateMetadata({ searchParams }: SP): Promise<Metadata> {
  const page = Math.max(1, Number((await searchParams).page) || 1)
  return {
    title: page > 1 ? `Барлық жаңалықтар — ${page}-бет` : 'Барлық жаңалықтар',
    description: 'TechTalQ: IT, жасанды интеллект, гаджеттер және стартаптар туралы соңғы жаңалықтар қазақ тілінде.',
    alternates: { canonical: page > 1 ? `/zhanalyq?page=${page}` : '/zhanalyq' },
  }
}

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
