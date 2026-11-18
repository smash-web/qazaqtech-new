import { ImageResponse } from 'next/og'
import { articleBySlug } from '@/lib/cms'
import { COVER_THEME } from '@/lib/cover'
import { loadFont } from '@/lib/ogFonts'
import { SITE } from '@/lib/site'
import { asCategory } from '@/lib/types'

// Автообложка 1200×675 (16:9): заголовок, рубрика, источники. Кэшируется CDN навсегда (?v=updatedAt).
const W = 1200
const H = 675

function titleSize(title: string) {
  const n = title.length
  if (n <= 50) return 68
  if (n <= 80) return 58
  if (n <= 110) return 50
  return 44
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const article = await articleBySlug((await params).slug)
  if (!article) return new Response('Not found', { status: 404 })

  const cat = asCategory(article.category)
  const { ink, sky, gold } = COVER_THEME
  const title = article.title.length > 140 ? `${article.title.slice(0, 137)}…` : article.title
  const sources = Array.from(new Set((article.sources || []).map((s) => s.name))).slice(0, 3).join(' · ')
  const label = (cat?.name || 'Технология').toUpperCase()
  const host = SITE.url.replace(/^https?:\/\//, '')
  const allText = `${label}${title}${sources}${host}0123456789·…`

  const [bold, regular, logo] = await Promise.all([
    loadFont('Inter', 800, allText), loadFont('Inter', 500, allText), loadFont('Space Grotesk', 700, 'TechTalQ'),
  ])
  const fonts = [
    bold && { name: 'Inter', data: bold, weight: 800 as const, style: 'normal' as const },
    regular && { name: 'Inter', data: regular, weight: 500 as const, style: 'normal' as const },
    logo && { name: 'Space Grotesk', data: logo, weight: 700 as const, style: 'normal' as const },
  ].filter(Boolean) as { name: string; data: ArrayBuffer; weight: 800 | 700 | 500; style: 'normal' }[]

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          padding: '64px 72px', color: '#fff', fontFamily: 'Inter', backgroundColor: ink, position: 'relative',
        }}
      >
        {/* крупное кольцо знака Q в углу и точка-сигнал */}
        <div style={{ position: 'absolute', right: -150, top: -170, width: 520, height: 520, borderRadius: 9999,
          border: `86px solid ${sky}24`, display: 'flex' }} />
        <div style={{ position: 'absolute', right: 86, top: 66, width: 48, height: 48, borderRadius: 9999,
          backgroundColor: sky, display: 'flex' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
          <svg width="52" height="52" viewBox="0 0 64 64" fill="none">
            <circle cx="27" cy="27" r="20" stroke="#fff" strokeWidth="9" />
            <circle cx="27" cy="27" r="4.2" fill={sky} />
            <path d="M39.5 39.5l15 15" stroke={gold} strokeWidth="8" strokeLinecap="round" />
          </svg>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 40, fontWeight: 700, display: 'flex' }}>
            <span>TechTal<span style={{ color: sky }}>Q</span></span>
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: 2.5, padding: '9px 16px', borderRadius: 8,
            backgroundColor: sky, color: ink, display: 'flex', marginLeft: 8 }}>
            {label}
          </div>
        </div>

        <div style={{ fontSize: titleSize(title), fontWeight: 800, lineHeight: 1.14, letterSpacing: -1.5,
          maxWidth: 1040, display: 'flex' }}>
          {title}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 24,
          fontWeight: 500, color: '#9FB0CC' }}>
          <div style={{ display: 'flex' }}>{sources}</div>
          <div style={{ display: 'flex' }}>{host}</div>
        </div>
        <div style={{ position: 'absolute', left: 72, bottom: 0, width: 120, height: 10, backgroundColor: gold,
          display: 'flex' }} />
      </div>
    ),
    {
      width: W,
      height: H,
      fonts: fonts.length ? fonts : undefined,
      headers: { 'Cache-Control': 'public, max-age=31536000, s-maxage=31536000, immutable' },
    },
  )
}
