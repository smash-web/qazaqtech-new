'use client'

import { useDocumentInfo, useField, useForm } from '@payloadcms/ui'

const SITE = process.env.NEXT_PUBLIC_SITE_URL || ''
const QUEUE = '/admin/collections/articles?where[status][equals]=review'

/** Одна большая кнопка вместо выбора статуса: «Опубликовать» ставит статус и сразу сохраняет. */
export function PublishButton() {
  const { value: status, setValue } = useField<string>({ path: 'status' })
  const { value: slug } = useField<string>({ path: 'slug' })
  const { submit, setModified } = useForm()
  const { id } = useDocumentInfo()

  const save = (next: string) => {
    const fromQueue = status === 'review' && next === 'published'
    setValue(next)
    setModified(true)
    setTimeout(async () => { // даём форме принять новый статус
      await submit()
      if (!fromQueue || !id) return
      // Статья из очереди проверки опубликована — сразу к следующей. Проверяем по серверу: при ошибке
      // сохранения (не заполнено обязательное поле) остаёмся на странице.
      try {
        const r = await fetch(`/api/articles/${id}?depth=0&select[status]=true`, { credentials: 'include', cache: 'no-store' })
        const d = r.ok ? await r.json() : null
        if (d?.status === 'published') window.location.assign(QUEUE)
      } catch { /* остаёмся на странице */ }
    }, 150)
  }

  if (status === 'published') {
    return (
      <div className="qt-pub">
        <p className="qt-pub__ok">✓ Опубликовано</p>
        {SITE && slug && <a className="qt-pub__link" href={`${SITE}/zhanalyq/${slug}`} target="_blank" rel="noreferrer">Открыть на сайте ↗</a>}
        <button type="button" className="qt-pub__btn qt-pub__btn--ghost" onClick={() => save('draft')}>Снять с публикации</button>
      </div>
    )
  }
  return (
    <div className="qt-pub">
      <button type="button" className="qt-pub__btn" onClick={() => save('published')}>Опубликовать</button>
      <p className="qt-pub__hint">Статья сразу появится на сайте. Кнопка «Сохранить» вверху — сохранить как черновик.</p>
    </div>
  )
}
