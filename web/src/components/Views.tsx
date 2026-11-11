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

// Общее хранилище свежих счётчиков: страницы сайта кэшируются, поэтому числа в карточках
// дозапрашиваются одним пакетным запросом после загрузки.
const fresh = new Map<string, number>()
const listeners = new Map<string, Set<(n: number) => void>>()
let pending = new Set<string>()
let timer: ReturnType<typeof setTimeout> | null = null

function publish(id: string, n: number) {
  fresh.set(id, n)
  listeners.get(id)?.forEach((fn) => fn(n))
}

function request(id: string) {
  pending.add(id)
  if (timer) return
  timer = setTimeout(() => {
    const ids = [...pending]
    pending = new Set()
    timer = null
    fetch(`/hit?ids=${ids.join(',')}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Record<string, number> | null) => {
        if (d) for (const [k, v] of Object.entries(d)) publish(k, Number(v))
      })
      .catch(() => {})
  }, 60)
}

/** Глазок с числом просмотров. С track — засчитывает просмотр (один раз за сессию браузера). */
export function Views({ id, initial = 0, track = false }: { id: number | string; initial?: number; track?: boolean }) {
  const key = String(id)
  const [views, setViews] = useState(initial)

  useEffect(() => {
    let set = listeners.get(key)
    if (!set) listeners.set(key, (set = new Set()))
    set.add(setViews)

    let counted = true
    if (track) {
      try {
        counted = !!sessionStorage.getItem(`qt-viewed-${key}`)
        if (!counted) sessionStorage.setItem(`qt-viewed-${key}`, '1')
      } catch { counted = false /* приватный режим: считаем без защиты от повтора */ }
    }
    if (track && !counted) {
      fetch(`/hit/${key}`, { method: 'POST', keepalive: true })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => { if (d && typeof d.views === 'number') publish(key, d.views) })
        .catch(() => {})
    } else {
      request(key)
    }
    // Возврат кнопкой «Назад» восстанавливает страницу из памяти браузера — обновляем числа и тогда
    const onShow = (e: PageTransitionEvent) => { if (e.persisted) request(key) }
    window.addEventListener('pageshow', onShow)
    return () => { set!.delete(setViews); window.removeEventListener('pageshow', onShow) }
  }, [key, track])

  return (
    <span className="views" title="Қаралым саны" aria-label={`${views} қаралым`}>
      <EyeIcon />{formatViews(views)}
    </span>
  )
}
