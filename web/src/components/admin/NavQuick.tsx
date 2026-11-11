import Link from 'next/link'
import type { Payload } from 'payload'

const A = '/admin/collections/articles'

/** Быстрые ссылки вверху бокового меню: очередь проверки и новая статья. */
export async function NavQuick({ payload }: { payload?: Payload }) {
  let review = 0
  try {
    if (payload) review = (await payload.count({ collection: 'articles', where: { status: { equals: 'review' } } })).totalDocs
  } catch { /* без счётчика ссылка всё равно работает */ }
  return (
    <div className="qt-nav">
      <Link className="qt-nav__link qt-nav__link--new" href={`${A}/create`}>＋ Новая статья</Link>
      <Link className="qt-nav__link" href={`${A}?where[status][equals]=review`}>
        На модерации{review > 0 && <span className="qt-nav__badge">{review}</span>}
      </Link>
      <Link className="qt-nav__link" href={`${A}?where[status][equals]=draft`}>Черновики</Link>
      <Link className="qt-nav__link" href={`${A}?where[status][equals]=published`}>Опубликованные</Link>
    </div>
  )
}
