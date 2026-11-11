import type { Payload } from 'payload'

type Props = { payload?: Payload; user?: { name?: string | null; email?: string; role?: string } | null }

const SITE = process.env.NEXT_PUBLIC_SITE_URL || ''
const A = '/admin/collections/articles'
const byStatus = (s: string) => `${A}?where[status][equals]=${s}`

/** Главный экран редакции: крупные действия и что требует внимания — вместо технического списка коллекций. */
export async function Dashboard({ payload, user }: Props) {
  let review = 0, drafts = 0, today = 0
  let queue: { id: number | string; title: string }[] = []
  try {
    if (payload) {
      const dayStart = new Date(Date.now() + 5 * 3600_000) // сутки по Алматы (UTC+5)
      dayStart.setUTCHours(0, 0, 0, 0)
      const since = new Date(dayStart.getTime() - 5 * 3600_000).toISOString()
      const [r, d, t, q] = await Promise.all([
        payload.count({ collection: 'articles', where: { status: { equals: 'review' } } }),
        payload.count({ collection: 'articles', where: { status: { equals: 'draft' } } }),
        payload.count({ collection: 'articles', where: { and: [{ status: { equals: 'published' } }, { publishedAt: { greater_than_equal: since } }] } }),
        payload.find({ collection: 'articles', where: { status: { equals: 'review' } }, sort: '-createdAt', limit: 5, depth: 0, select: { title: true } }),
      ])
      review = r.totalDocs; drafts = d.totalDocs; today = t.totalDocs
      queue = q.docs.map((x) => ({ id: x.id, title: String((x as { title?: string }).title || '') }))
    }
  } catch { /* счётчики не критичны: кнопки ниже работают и без них */ }
  const name = user?.name || user?.email?.split('@')[0] || ''
  return (
    <section className="qt-dash">
      <h2 className="qt-dash__hello">Сәлем{name ? `, ${name}` : ''}! 👋</h2>
      <a className="qt-dash__new" href={`${A}/create`}>
        <span className="qt-dash__plus" aria-hidden="true">＋</span>
        <span><b>Новая статья</b><small>Фото, заголовок, текст — и «Опубликовать»</small></span>
      </a>
      <div className="qt-dash__grid">
        <a className={`qt-dash__card${review ? ' is-warn' : ''}`} href={byStatus('review')}><b>{review}</b><span>Ждут проверки</span></a>
        <a className="qt-dash__card" href={byStatus('draft')}><b>{drafts}</b><span>Черновики</span></a>
        <a className="qt-dash__card" href={byStatus('published')}><b>{today}</b><span>Вышло сегодня</span></a>
        <a className="qt-dash__card" href="/admin/collections/media/create"><b>🖼</b><span>Загрузить фото</span></a>
      </div>
      {!!queue.length && (
        <div className="qt-dash__queue">
          <h3>Проверьте и опубликуйте</h3>
          {queue.map((q) => <a key={q.id} href={`${A}/${q.id}`}>{q.title}<span aria-hidden="true">›</span></a>)}
          {review > queue.length && <a className="qt-dash__more" href={byStatus('review')}>Все на проверке ({review})</a>}
        </div>
      )}
      {SITE && <a className="qt-dash__site" href={SITE} target="_blank" rel="noreferrer">Открыть сайт ↗</a>}
    </section>
  )
}
