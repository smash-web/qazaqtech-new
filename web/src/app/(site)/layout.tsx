import type { Metadata } from 'next'
import { Footer } from '@/components/Footer'
import { Header } from '@/components/Header'
import { SITE } from '@/lib/site'
import './globals.css'

// Рендер по запросу; данные кэшируются в lib/cms.ts и сбрасываются при публикации
export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: { default: `${SITE.name} — ${SITE.tagline}`, template: `%s — ${SITE.name}` },
  description: 'Жасанды интеллект, IT-компаниялар, стартаптар, киберқауіпсіздік және гаджеттер туралы күнделікті жаңалықтар қазақ тілінде.',
  alternates: { canonical: '/', types: { 'application/rss+xml': '/rss.xml' } },
  openGraph: { siteName: SITE.name, locale: SITE.locale, type: 'website' },
}

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="kk">
      <body>
        <Header />
        <main className="container main">{children}</main>
        <Footer />
      </body>
    </html>
  )
}
