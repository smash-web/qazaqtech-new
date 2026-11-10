'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

/** Горизонтальное меню рубрик с подсветкой текущей */
export function NavLinks({ items }: { items: { href: string; label: string }[] }) {
  const pathname = usePathname()
  return (
    <>
      {items.map((i) => {
        const active = i.href === '/' ? pathname === '/' : pathname.startsWith(i.href)
        return (
          <Link key={i.href} href={i.href} className={active ? 'is-active' : undefined} aria-current={active ? 'page' : undefined}>
            {i.label}
          </Link>
        )
      })}
    </>
  )
}
