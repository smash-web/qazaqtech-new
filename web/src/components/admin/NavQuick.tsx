import type { Payload } from 'payload'

const A = '/admin/collections/articles'

/**
 * Быстрые ссылки вверху бокового меню: очередь проверки и новая статья.
 * Обычные <a>, а не next/link: при переходе внутри того же списка Payload не применял фильтр
 * и не закрывал меню на телефоне — полная загрузка страницы делает и то и другое.
 */
export async function NavQuick({ payload }: { payload?: Payload }) {
  let review = 0
  try {
    if (payload) review = (await payload.count({ collection: 'articles', where: { status: { equals: 'review' } } })).totalDocs
  } catch { /* без счётчика ссылка всё равно работает */ }
  return (
    <div className="qt-nav">
      <a className="qt-nav__link qt-nav__link--new" href={`${A}/create`}>＋ Новая статья</a>
      <a className="qt-nav__link" href={`${A}?where[status][equals]=review`}>
        На модерации{review > 0 && <span className="qt-nav__badge">{review}</span>}
      </a>
      <a className="qt-nav__link" href={`${A}?where[status][equals]=draft`}>Черновики</a>
      <a className="qt-nav__link" href={`${A}?where[status][equals]=published`}>Опубликованные</a>
    </div>
  )
}
