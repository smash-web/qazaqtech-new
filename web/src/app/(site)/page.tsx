import Link from 'next/link'
import { ArticleCard } from '@/components/ArticleCard'
import { latestArticles } from '@/lib/cms'


export default async function Home() {
  const { docs } = await latestArticles({ limit: 25 })
  if (!docs.length) return <p className="empty">Жаңалықтар әзірге жоқ.</p>
  const [hero, ...rest] = docs
  const side = rest.slice(0, 4)
  const feed = rest.slice(4)
  return (
    <>
      <section className="top">
        <ArticleCard article={hero} variant="hero" />
        <div className="top__side">
          {side.map((a) => <ArticleCard key={a.id} article={a} variant="compact" />)}
        </div>
      </section>
      <h2 className="section-title">Соңғы жаңалықтар</h2>
      <section className="grid">
        {feed.map((a) => <ArticleCard key={a.id} article={a} />)}
      </section>
      <p className="more"><Link href="/zhanalyq?page=2">Барлық жаңалықтар →</Link></p>
    </>
  )
}
