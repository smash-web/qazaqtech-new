import Link from 'next/link'
import { categories } from '@/lib/cms'
import { SITE } from '@/lib/site'

export async function Header() {
  const cats = await categories()
  return (
    <header className="header">
      <div className="container header__top">
        <Link href="/" className="logo">{SITE.name}</Link>
        <span className="header__tagline">{SITE.tagline}</span>
        <form action="/izdeu" className="search" role="search">
          <input name="q" type="search" placeholder="Іздеу…" aria-label="Сайттан іздеу" />
        </form>
      </div>
      <nav className="container nav" aria-label="Айдарлар">
        <Link href="/zhanalyq">Барлығы</Link>
        {cats.map((c) => (
          <Link key={c.id} href={`/sanat/${c.slug}`}>{c.name}</Link>
        ))}
      </nav>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <p>
          <strong>{SITE.name}</strong> — {SITE.tagline.toLowerCase()}. Материалдар халықаралық басылымдардың
          жарияланымдары негізінде жасанды интеллект көмегімен дайындалады; әр мақалада түпнұсқа дереккөздерге
          сілтеме беріледі.
        </p>
        <p>
          <Link href="/rss.xml">RSS</Link> · © {new Date().getFullYear()} {SITE.name}
        </p>
      </div>
    </footer>
  )
}
