'use client'

import { useField, useForm } from '@payloadcms/ui'

type Net = { key: 'instagram' | 'tiktok'; label: string }
const NETS: Net[] = [
  { key: 'instagram', label: 'В Instagram' },
  { key: 'tiktok', label: 'В TikTok (черновик)' },
]

/** Редактор сам выбирает, что уйдёт в Instagram и TikTok: кнопка ставит заявку, конвейер публикует в течение 30 минут. */
export function SocialShare() {
  const { value: status } = useField<string>({ path: 'status' })
  const { submit, setModified } = useForm()
  const fields = {
    instagram: { req: useField<string>({ path: 'instagramRequestedAt' }), st: useField<string>({ path: 'instagramStatus' }) },
    tiktok: { req: useField<string>({ path: 'tiktokRequestedAt' }), st: useField<string>({ path: 'tiktokStatus' }) },
  }

  const request = (key: Net['key'], cancel = false) => {
    fields[key].req.setValue(cancel ? null : new Date().toISOString())
    fields[key].st.setValue(cancel ? '' : 'В очереди — уйдёт в течение 30 минут')
    setModified(true)
    setTimeout(() => submit(), 150)
  }

  return (
    <div className="qt-share">
      <p className="qt-share__title">Соцсети</p>
      {status !== 'published' && <p className="qt-share__hint">Кнопки заработают после публикации статьи на сайте.</p>}
      {NETS.map(({ key, label }) => {
        const req = fields[key].req.value
        const st = fields[key].st.value || ''
        const done = st.startsWith('✓')
        const queued = Boolean(req) && !done && !st.startsWith('✕')
        return (
          <div key={key} className="qt-share__row">
            {!req || st.startsWith('✕') ? (
              <button type="button" className="qt-share__btn" disabled={status !== 'published'} onClick={() => request(key)}>
                {st.startsWith('✕') ? `Повторить: ${label.toLowerCase()}` : label}
              </button>
            ) : (
              <div className={`qt-share__state${done ? ' is-done' : ''}`}>
                <span>{label}</span>
                {queued && <button type="button" className="qt-share__cancel" onClick={() => request(key, true)}>отменить</button>}
              </div>
            )}
            {st && <p className={`qt-share__status${st.startsWith('✕') ? ' is-error' : ''}`}>{st}</p>}
          </div>
        )
      })}
    </div>
  )
}
