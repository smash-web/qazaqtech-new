import Link from 'next/link'
import { categories, latestArticles, pages, siteSettings } from '@/lib/cms'
import { formatToday, SITE } from '@/lib/site'
import { MobileMenu } from './MobileMenu'
import { SearchBox } from './SearchBox'
import { NavLinks } from './NavLinks'
import { SocialLinks } from './SocialLinks'

export async function Header() {
  const [cats, pgs, settings, latest] = await Promise.all([
    categories(), pages(), siteSettings(), latestArticles({ limit: 6 }),
  ])
  const sections = [{ href: '/', label: 'Басты бет' }, { href: '/zhanalyq', label: 'Барлық жаңалықтар' },
    ...cats.map((c) => ({ href: `/sanat/${c.slug}`, label: c.name }))]
  const infoPages = pgs.filter((p) => p.showInFooter !== false).map((p) => ({ href: `/aqparat/${p.slug}`, label: p.title }))

  return (
    <header className="header">
      <div className="topbar">
        <div className="container topbar__inner">
          <span className="topbar__date">{formatToday()}</span>
          <nav className="topbar__links" aria-label="Редакция">
            {infoPages.slice(0, 3).map((p) => <Link key={p.href} href={p.href}>{p.label}</Link>)}
            <a href="/rss.xml">RSS</a>
          </nav>
          <SocialLinks social={settings?.social} className="topbar__social" />
        </div>
      </div>

      <div className="container header__main">
        <MobileMenu sections={sections} pages={infoPages} />
        <Link href="/" className="logo" aria-label={`${SITE.name} — басты бет`}>
          <span className="logo__mark" aria-hidden="true">Q</span>
          <span className="logo__text"><span className="logo__accent">Qazaq</span>Tech</span>
        </Link>
        <span className="header__tagline">{SITE.tagline}</span>
        <SearchBox />
      </div>

      <nav className="nav-wrap" aria-label="Айдарлар">
        <div className="container nav">
          <NavLinks items={[{ href: '/zhanalyq', label: 'Барлығы' }, ...cats.map((c) => ({ href: `/sanat/${c.slug}`, label: c.name }))]} />
        </div>
      </nav>

      {!!latest.docs.length && (
        <div className="ticker" aria-label="Соңғы тақырыптар">
          <div className="container ticker__inner">
            <span className="ticker__label">Соңғы</span>
            <div className="ticker__track">
              {latest.docs.map((a) => (
                <Link key={a.id} href={`/zhanalyq/${a.slug}`} className="ticker__item">{a.title}</Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
