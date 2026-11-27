import type { Metadata, Viewport } from 'next'
import { Inter, Space_Grotesk } from 'next/font/google'
import { Footer } from '@/components/Footer'
import { Header } from '@/components/Header'
import { SITE } from '@/lib/site'
import './globals.css'

// Брендбук: текст — Inter (с казахскими буквами), логотип и латинские заголовки — Space Grotesk Bold
const inter = Inter({ subsets: ['latin', 'cyrillic', 'cyrillic-ext'], display: 'swap', variable: '--font-inter' })
const grotesk = Space_Grotesk({ subsets: ['latin'], weight: ['700'], display: 'swap', variable: '--font-grotesk' })

export const viewport: Viewport = { themeColor: '#0B1B3A' }

// Рендер по запросу; данные кэшируются в lib/cms.ts и сбрасываются при публикации
export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: { default: `${SITE.name} — ${SITE.tagline}`, template: `%s — ${SITE.name}` },
  description: 'Жасанды интеллект, IT-компаниялар, стартаптар, киберқауіпсіздік және гаджеттер туралы күнделікті жаңалықтар қазақ тілінде.',
  alternates: { canonical: '/', types: { 'application/rss+xml': '/rss.xml' } },
  openGraph: { siteName: SITE.name, locale: SITE.locale, type: 'website', images: ['/ig-static/avatar.jpg'] },
  twitter: { card: 'summary_large_image' },
  robots: { index: true, follow: true, googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1 } },
  keywords: ['IT жаңалықтары', 'технология жаңалықтары', 'жасанды интеллект', 'қазақша жаңалықтар', 'гаджеттер', 'киберқауіпсіздік', 'стартаптар'],
  // коды подтверждения из Google Search Console и Яндекс.Вебмастера (переменные окружения Vercel)
  verification: {
    google: process.env.GOOGLE_SITE_VERIFICATION || undefined,
    yandex: process.env.YANDEX_VERIFICATION || undefined,
  },
}

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="kk" className={`${inter.variable} ${grotesk.variable}`}>
      <body>
        <Header />
        <main className="container main">{children}</main>
        <Footer />
      </body>
    </html>
  )
}
