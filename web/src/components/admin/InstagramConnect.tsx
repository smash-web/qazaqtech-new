'use client'

import { useFormFields } from '@payloadcms/ui'

const fmt = (v: unknown) => (typeof v === 'string' && v ? new Date(v).toLocaleString('ru-RU', { timeZone: 'Asia/Almaty' }) : '—')

/** Статус подключения Instagram и кнопка «Подключить» (вход в окне Meta — пароль сайт не видит). */
export function InstagramConnect() {
  const f = useFormFields(([fields]) => ({
    username: fields.username?.value as string | undefined,
    expires: fields.tokenExpiresAt?.value,
    lastPost: fields.lastPostAt?.value,
    lastError: fields.lastError?.value as string | undefined,
  }))
  const qs = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
  const flash = qs?.get('ig_error') || ''
  const ok = qs?.get('ig') === 'connected'
  return (
    <div className="qt-ig">
      {f.username ? (
        <p className="qt-ig__status">
          Подключён аккаунт <a href={`https://www.instagram.com/${f.username}/`} target="_blank" rel="noopener"><b>@{f.username}</b></a>
          <br /><small>{f.expires ? `Доступ действует до ${fmt(f.expires)}.` : 'Доступ бессрочный.'} Последний пост: {fmt(f.lastPost)}.</small>
        </p>
      ) : (
        <p className="qt-ig__status">Instagram не подключён.</p>
      )}
      {ok && <p className="qt-ig__ok">Готово: Instagram подключён. Включите «Публиковать в Instagram» и сохраните.</p>}
      {(flash || f.lastError) && <p className="qt-ig__err">{flash || f.lastError}</p>}
      <a className="qt-ig__btn" href="/instagram/connect">{f.username ? 'Переподключить Instagram' : 'Подключить Instagram'}</a>
    </div>
  )
}
