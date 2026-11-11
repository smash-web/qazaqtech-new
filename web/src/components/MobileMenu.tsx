'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { SearchBox } from './SearchBox'

type Item = { href: string; label: string }

export function MobileMenu({ sections, pages }: { sections: Item[]; pages: Item[] }) {
  const [open, setOpen] = useState(false)
  const pathname = usePathname()

  useEffect(() => setOpen(false), [pathname])
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  return (
    <>
      <button className="burger" aria-label={open ? 'Мәзірді жабу' : 'Мәзірді ашу'} aria-expanded={open}
        onClick={() => setOpen((v) => !v)}>
        {/* SVG, а не span-полоски: в Safari на iOS пустые flex-элементы внутри <button> не отрисовываются */}
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" aria-hidden="true">
          {open ? <path d="M3 3l18 18M21 3L3 21" /> : <path d="M1 3h22M1 12h22M1 21h22" />}
        </svg>
      </button>
      {open && (
        <div className="drawer" role="dialog" aria-modal="true" aria-label="Мәзір">
          <SearchBox className="drawer__search" placeholder="Сайттан іздеу…" />
          <p className="drawer__label">Айдарлар</p>
          <nav className="drawer__list">
            {sections.map((s) => (
              <Link key={s.href} href={s.href} className={pathname === s.href ? 'is-active' : undefined}>{s.label}</Link>
            ))}
          </nav>
          {!!pages.length && (
            <>
              <p className="drawer__label">Редакция</p>
              <nav className="drawer__list drawer__list--small">
                {pages.map((p) => <Link key={p.href} href={p.href}>{p.label}</Link>)}
                <a href="/rss.xml">RSS-таспа</a>
              </nav>
            </>
          )}
        </div>
      )}
    </>
  )
}
