import Link from 'next/link'
import { categories, pages, siteSettings } from '@/lib/cms'
import { SITE } from '@/lib/site'
import { SocialLinks } from './SocialLinks'

export async function Footer() {
  const [cats, pgs, settings] = await Promise.all([categories(), pages(), siteSettings()])
  const info = pgs.filter((p) => p.showInFooter !== false)
  return (
    <footer className="footer">
      <div className="container footer__grid">
        <div className="footer__brand">
          <Link href="/" className="logo logo--footer">
            <span className="logo__mark" aria-hidden="true">Q</span>
            <span className="logo__text"><span className="logo__accent">Qazaq</span>Tech</span>
          </Link>
          <p>{settings?.about || SITE.tagline}</p>
          <SocialLinks social={settings?.social} className="footer__social" />
        </div>
        <div>
          <h3>Айдарлар</h3>
          <ul>{cats.map((c) => <li key={c.id}><Link href={`/sanat/${c.slug}`}>{c.name}</Link></li>)}</ul>
        </div>
        <div>
          <h3>Редакция</h3>
          <ul>
            {info.map((p) => <li key={p.id}><Link href={`/aqparat/${p.slug}`}>{p.title}</Link></li>)}
            {settings?.email && <li><a href={`mailto:${settings.email}`}>{settings.email}</a></li>}
            {settings?.adsEmail && <li>Жарнама: <a href={`mailto:${settings.adsEmail}`}>{settings.adsEmail}</a></li>}
          </ul>
        </div>
        <div>
          <h3>Жазылу</h3>
          <ul>
            <li><a href="/rss.xml">RSS-таспа</a></li>
            <li><Link href="/zhanalyq">Барлық жаңалықтар</Link></li>
            {settings?.social?.telegram && <li><a href={settings.social.telegram} target="_blank" rel="noopener">Telegram-арна</a></li>}
          </ul>
        </div>
      </div>
      <div className="container footer__bottom">
        <span>© {new Date().getFullYear()} {SITE.name}. Материалдарды пайдаланғанда сілтеме беру міндетті.</span>
        <span>Жаңалықтар халықаралық басылымдар негізінде ЖИ көмегімен дайындалады.</span>
      </div>
    </footer>
  )
}
