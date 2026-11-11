'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useId, useRef, useState } from 'react'
import { timeAgo } from '@/lib/site'

type Item = { title: string; slug: string; category: string | null; publishedAt: string | null }

function Highlight({ text, q }: { text: string; q: string }) {
  const i = text.toLowerCase().indexOf(q.toLowerCase())
  if (i < 0) return <>{text}</>
  return <>{text.slice(0, i)}<mark>{text.slice(i, i + q.length)}</mark>{text.slice(i + q.length)}</>
}

/** Поле поиска с подсказками при вводе. Enter без выбора — обычная страница результатов /izdeu. */
export function SearchBox({ className = 'search', placeholder = 'Іздеу…' }: { className?: string; placeholder?: string }) {
  const router = useRouter()
  const listId = useId()
  const box = useRef<HTMLFormElement>(null)
  const [q, setQ] = useState('')
  const [items, setItems] = useState<Item[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(-1)
  const term = q.trim()

  useEffect(() => {
    if (term.length < 2) { setItems([]); setLoading(false); return }
    setLoading(true)
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      fetch(`/suggest?q=${encodeURIComponent(term)}`, { signal: ctrl.signal })
        .then((r) => (r.ok ? r.json() : { items: [] }))
        .then((d) => { setItems(d.items || []); setActive(-1); setLoading(false) })
        .catch(() => {})
    }, 220)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [term])

  useEffect(() => {
    const onDown = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [])

  const go = (href: string) => { setOpen(false); setQ(''); router.push(href) }
  const all = `/izdeu?q=${encodeURIComponent(term)}`
  const show = open && term.length >= 2

  return (
    <form ref={box} action="/izdeu" role="search" className={`${className} searchbox`}
      onSubmit={(e) => {
        if (active >= 0 && items[active]) { e.preventDefault(); go(`/zhanalyq/${items[active].slug}`) } else setOpen(false)
      }}>
      <input name="q" type="search" value={q} placeholder={placeholder} aria-label="Сайттан іздеу" autoComplete="off"
        role="combobox" aria-expanded={show} aria-controls={listId} aria-autocomplete="list"
        onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setOpen(false)
          else if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); setOpen(true); setActive((i) => (i + 1) % items.length) }
          else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); setActive((i) => (i <= 0 ? items.length - 1 : i - 1)) }
        }} />
      {show && (
        <div className="suggest" id={listId} role="listbox">
          {items.map((it, i) => (
            <Link key={it.slug} href={`/zhanalyq/${it.slug}`} role="option" aria-selected={i === active}
              className={`suggest__item${i === active ? ' is-active' : ''}`}
              onClick={() => { setOpen(false); setQ('') }} onMouseEnter={() => setActive(i)}>
              <span className="suggest__title"><Highlight text={it.title} q={term} /></span>
              <span className="suggest__meta">{[it.category, timeAgo(it.publishedAt)].filter(Boolean).join(' · ')}</span>
            </Link>
          ))}
          {!items.length && <p className="suggest__empty">{loading ? 'Іздеу…' : 'Ештеңе табылмады'}</p>}
          {!!items.length && (
            <Link href={all} className="suggest__all" onClick={() => setOpen(false)}>Барлық нәтижелер: «{term}» →</Link>
          )}
        </div>
      )}
    </form>
  )
}
