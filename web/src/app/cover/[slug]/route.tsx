import { ImageResponse } from 'next/og'
import { articleBySlug } from '@/lib/cms'
import { CATEGORY_THEME, DEFAULT_THEME } from '@/lib/cover'
import { SITE } from '@/lib/site'
import { asCategory } from '@/lib/types'

// Автообложка 1200×675 (16:9): заголовок, рубрика, источники. Кэшируется CDN навсегда (?v=updatedAt).
const W = 1200
const H = 675

const fontCache = new Map<string, Promise<ArrayBuffer | null>>()

/** Шрифт Noto Sans с поддержкой казахских букв; Google Fonts отдаёт только нужные глифы (параметр text) */
function loadFont(weight: number, text: string): Promise<ArrayBuffer | null> {
  const key = `${weight}:${text}`
  if (!fontCache.has(key)) {
    fontCache.set(key, (async () => {
      try {
        const url = `https://fonts.googleapis.com/css2?family=Noto+Sans:wght@${weight}&text=${encodeURIComponent(text)}`
        const css = await (await fetch(url)).text()
        const src = css.match(/src: url\((.+?)\) format\('(opentype|truetype)'\)/)
        if (!src) return null
        const res = await fetch(src[1])
        return res.ok ? await res.arrayBuffer() : null
      } catch {
        return null
      }
    })())
    if (fontCache.size > 200) fontCache.delete(fontCache.keys().next().value as string)
  }
  return fontCache.get(key)!
}

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
  const [from, to, accent] = CATEGORY_THEME[cat?.slug || ''] || DEFAULT_THEME
  const title = article.title.length > 140 ? `${article.title.slice(0, 137)}…` : article.title
  const sources = Array.from(new Set((article.sources || []).map((s) => s.name))).slice(0, 3).join(' · ')
  const label = cat?.name || 'Технология'
  const allText = `${SITE.name}${label}${title}${sources}${SITE.url.replace(/^https?:\/\//, '')}0123456789·…`

  const [bold, regular] = await Promise.all([loadFont(800, allText), loadFont(500, allText)])
  const fonts = [
    bold && { name: 'Noto Sans', data: bold, weight: 800 as const, style: 'normal' as const },
    regular && { name: 'Noto Sans', data: regular, weight: 500 as const, style: 'normal' as const },
  ].filter(Boolean) as { name: string; data: ArrayBuffer; weight: 800 | 500; style: 'normal' }[]

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          padding: '64px 72px', color: '#fff', fontFamily: 'Noto Sans',
          backgroundImage: `linear-gradient(135deg, ${from} 0%, ${to} 100%)`, position: 'relative',
        }}
      >
        {/* декоративная сетка и круг */}
        <div style={{ position: 'absolute', right: -160, top: -160, width: 560, height: 560, borderRadius: 9999,
          border: `2px solid ${accent}33`, display: 'flex' }} />
        <div style={{ position: 'absolute', right: -60, top: -60, width: 360, height: 360, borderRadius: 9999,
          backgroundColor: `${accent}1a`, display: 'flex' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: -1, display: 'flex' }}>
            <span style={{ color: accent }}>Qazaq</span>
            <span>Tech</span>
          </div>
          <div style={{ fontSize: 24, fontWeight: 500, padding: '8px 20px', borderRadius: 9999,
            backgroundColor: `${accent}26`, color: accent, border: `1px solid ${accent}66`, display: 'flex' }}>
            {label}
          </div>
        </div>

        <div style={{ fontSize: titleSize(title), fontWeight: 800, lineHeight: 1.15, letterSpacing: -1.5,
          maxWidth: 1040, display: 'flex' }}>
          {title}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 24,
          fontWeight: 500, color: '#ffffffb3' }}>
          <div style={{ display: 'flex' }}>{sources}</div>
          <div style={{ display: 'flex' }}>{SITE.url.replace(/^https?:\/\//, '')}</div>
        </div>
        <div style={{ position: 'absolute', left: 0, bottom: 0, width: '100%', height: 8, backgroundColor: accent,
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
