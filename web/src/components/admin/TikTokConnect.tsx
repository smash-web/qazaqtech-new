'use client'

import { useFormFields } from '@payloadcms/ui'

const fmt = (v: unknown) => (typeof v === 'string' && v ? new Date(v).toLocaleString('ru-RU', { timeZone: 'Asia/Almaty' }) : '—')

/** Статус подключения TikTok и кнопка «Подключить» (вход на странице TikTok — пароль сайт не видит). */
export function TikTokConnect() {
  const f = useFormFields(([fields]) => ({
    name: fields.displayName?.value as string | undefined,
    refreshExpires: fields.refreshExpiresAt?.value,
    lastPost: fields.lastPostAt?.value,
    lastError: fields.lastError?.value as string | undefined,
  }))
  const qs = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
  const flash = qs?.get('tt_error') || ''
  const ok = qs?.get('tt') === 'connected'
  return (
    <div className="qt-ig">
      {f.name ? (
        <p className="qt-ig__status">
          Подключён аккаунт TikTok <b>{f.name}</b>
          <br /><small>Доступ продлевается автоматически, переподключить нужно до {fmt(f.refreshExpires)}. Последний черновик: {fmt(f.lastPost)}.</small>
        </p>
      ) : (
        <p className="qt-ig__status">TikTok не подключён.</p>
      )}
      {ok && <p className="qt-ig__ok">Готово: TikTok подключён. Включите «Отправлять черновики в TikTok» и сохраните.</p>}
      {(flash || f.lastError) && <p className="qt-ig__err">{flash || f.lastError}</p>}
      <a className="qt-ig__btn" href="/tiktok/connect">{f.name ? 'Переподключить TikTok' : 'Подключить TikTok'}</a>
    </div>
  )
}
