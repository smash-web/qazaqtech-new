import Link from 'next/link'
import { ArticleCard } from '@/components/ArticleCard'
import { SourcesPanel, SubscribePanel, TagsPanel } from '@/components/Panels'
import { categories, latestArticles } from '@/lib/cms'

export default async function Home() {
  const [{ docs }, cats] = await Promise.all([latestArticles({ limit: 25 }), categories()])
  if (!docs.length) {
    return (
      <>
        <p className="empty">Жаңалықтар жақында жарияланады.</p>
        <div className="panels"><SubscribePanel /><SourcesPanel /></div>
      </>
    )
  }
  const [hero, ...rest] = docs
  const side = rest.slice(0, 5)
  const feed = rest.slice(5, 14)
  const shown = [hero, ...side, ...feed].map((a) => a.id)

  // Блоки рубрик: только непустые, без статей, уже показанных выше
  const blocks = (
    await Promise.all(
      cats.map(async (c) => ({ cat: c, docs: (await latestArticles({ category: c.id, limit: 4, exclude: shown })).docs })),
    )
  ).filter((b) => b.docs.length)

  return (
    <>
      <section className="top">
        <ArticleCard article={hero} variant="hero" />
        {!!side.length && (
          <div className="top__side">
            <h2 className="side-title">Соңғы жаңалықтар</h2>
            {side.map((a) => <ArticleCard key={a.id} article={a} variant="list" />)}
            <Link href="/zhanalyq" className="side-more">Барлық жаңалықтар →</Link>
          </div>
        )}
      </section>

      {!!feed.length && (
        <section>
          <h2 className="section-title">Күн жаңалықтары</h2>
          <div className="grid">{feed.map((a) => <ArticleCard key={a.id} article={a} />)}</div>
        </section>
      )}

      {blocks.map(({ cat, docs: list }) => (
        <section key={cat.id} className="cat-block">
          <div className="section-head">
            <h2 className="section-title"><Link href={`/sanat/${cat.slug}`}>{cat.name}</Link></h2>
            <Link href={`/sanat/${cat.slug}`} className="section-more">Барлығы →</Link>
          </div>
          <div className="grid grid--4">{list.map((a) => <ArticleCard key={a.id} article={a} />)}</div>
        </section>
      ))}

      <div className="panels">
        <TagsPanel />
        <SubscribePanel />
        <SourcesPanel />
      </div>
    </>
  )
}
