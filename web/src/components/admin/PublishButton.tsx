'use client'

import { useField, useForm } from '@payloadcms/ui'

const SITE = process.env.NEXT_PUBLIC_SITE_URL || ''

/** Одна большая кнопка вместо выбора статуса: «Опубликовать» ставит статус и сразу сохраняет. */
export function PublishButton() {
  const { value: status, setValue } = useField<string>({ path: 'status' })
  const { value: slug } = useField<string>({ path: 'slug' })
  const { submit, setModified } = useForm()

  const save = (next: string) => {
    setValue(next)
    setModified(true)
    setTimeout(() => { void submit() }, 150) // даём форме принять новый статус
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
