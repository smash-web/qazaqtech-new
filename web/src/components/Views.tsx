'use client'

import { useEffect, useState } from 'react'

export function formatViews(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace('.0', '')} млн`
  if (n >= 10_000) return `${Math.round(n / 1000)} мың`
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace('.0', '')} мың`
  return String(n)
}

export function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

/** Глазок с числом просмотров. С track — засчитывает просмотр (один раз за сессию браузера). */
export function Views({ id, initial = 0, track = false }: { id: number | string; initial?: number; track?: boolean }) {
  const [views, setViews] = useState(initial)

  useEffect(() => {
    if (!track) return
    const key = `qt-viewed-${id}`
    try {
      if (sessionStorage.getItem(key)) return
      sessionStorage.setItem(key, '1')
    } catch { /* приватный режим: считаем без защиты от повтора */ }
    fetch(`/hit/${id}`, { method: 'POST', keepalive: true })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && typeof d.views === 'number') setViews(d.views) })
      .catch(() => {})
  }, [id, track])

  return (
    <span className="views" title="Қаралым саны" aria-label={`${views} қаралым`}>
      <EyeIcon />{formatViews(views)}
    </span>
  )
}
