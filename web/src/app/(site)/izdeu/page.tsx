import type { Metadata } from 'next'
import { ArticleCard } from '@/components/ArticleCard'
import { Pagination } from '@/components/Pagination'
import { searchArticles } from '@/lib/cms'

export const metadata: Metadata = { title: 'Іздеу', robots: { index: false } }

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string; page?: string }> }) {
  const sp = await searchParams
  const q = (sp.q || '').trim().slice(0, 100)
  const page = Math.max(1, Number(sp.page) || 1)
  const res = q.length >= 2 ? await searchArticles(q, page) : null
  return (
    <>
      <h1 className="section-title">Іздеу{q && `: «${q}»`}</h1>
      {!res && <p className="empty">Кемінде 2 таңба енгізіңіз.</p>}
      {res && !res.docs.length && <p className="empty">Ештеңе табылмады.</p>}
      {res && (
        <>
          <section className="grid">{res.docs.map((a) => <ArticleCard key={a.id} article={a} />)}</section>
          <Pagination page={page} totalPages={res.totalPages} basePath="/izdeu" query={{ q }} />
        </>
      )}
    </>
  )
}
