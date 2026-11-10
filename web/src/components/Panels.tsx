import Link from 'next/link'
import { popularTags, siteSettings, watchedSources } from '@/lib/cms'

/** «Танымал тақырыптар» — облако тегов из последних публикаций */
export async function TagsPanel({ limit = 18 }: { limit?: number }) {
  const tags = await popularTags(limit)
  if (!tags.length) return null
  return (
    <section className="panel">
      <h2 className="panel__title">Танымал тақырыптар</h2>
      <div className="chips">
        {tags.map((t) => (
          <Link key={t.tag} href={`/teg/${encodeURIComponent(t.tag)}`} className="chip">#{t.tag}</Link>
        ))}
      </div>
    </section>
  )
}

/** «Біз бақылайтын басылымдар» — реальный список источников из админки */
export async function SourcesPanel() {
  const sources = await watchedSources()
  if (!sources.length) return null
  return (
    <section className="panel">
      <h2 className="panel__title">Біз бақылайтын басылымдар</h2>
      <p className="panel__text">Жаңалықтарды әлемдегі {sources.length} жетекші технологиялық басылымнан күн сайын іріктейміз.</p>
      <div className="chips chips--plain">
        {sources.map((s) =>
          s.siteUrl ? (
            <a key={s.name} href={s.siteUrl} target="_blank" rel="noopener nofollow" className="chip chip--plain">{s.name}</a>
          ) : (
            <span key={s.name} className="chip chip--plain">{s.name}</span>
          ),
        )}
      </div>
    </section>
  )
}

/** Блок подписки: RSS всегда, Telegram — если указан в настройках */
export async function SubscribePanel() {
  const settings = await siteSettings()
  const tg = settings?.social?.telegram
  return (
    <section className="panel panel--accent">
      <h2 className="panel__title">Жаңалықтардан қалмаңыз</h2>
      <p className="panel__text">Күн сайын 15–20 маңызды технология жаңалығы — қазақ тілінде, қысқа әрі түсінікті.</p>
      <div className="panel__actions">
        {tg && <a href={tg} target="_blank" rel="noopener" className="btn">Telegram-арнаға жазылу</a>}
        <a href="/rss.xml" className={tg ? 'btn btn--ghost' : 'btn'}>RSS арқылы оқу</a>
      </div>
    </section>
  )
}
