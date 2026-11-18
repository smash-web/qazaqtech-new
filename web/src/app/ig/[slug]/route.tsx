import { ImageResponse } from 'next/og'
import sharp from 'sharp'
import { articleBySlug } from '@/lib/cms'
import { COVER_THEME } from '@/lib/cover'
import { loadFont } from '@/lib/ogFonts'
import { SITE } from '@/lib/site'
import { asMedia } from '@/lib/types'

// Картинка для поста в Instagram: 1080×1350 (4:5), JPEG — PNG и WebP Instagram API не принимает.
// Стиль новостных пабликов: фото на весь кадр, сверху логотип, снизу затемнение и крупный заголовок
// заглавными буквами; последние слова — на бирюзовой плашке. Цвета — брендбук TechTalQ.
const W = 1080
const H = 1350
const PAD = 72

/** Фото статьи → JPEG data URL на весь кадр (Satori не читает WebP) */
async function photoDataUrl(src: string | null | undefined): Promise<string | null> {
  if (!src) return null
  try {
    const url = src.startsWith('http') ? src : `${SITE.url}${src}`
    const res = await fetch(url)
    if (!res.ok) return null
    const jpg = await sharp(Buffer.from(await res.arrayBuffer()))
      .resize(W, H, { fit: 'cover', position: 'attention' })
      .jpeg({ quality: 86 })
      .toBuffer()
    return `data:image/jpeg;base64,${jpg.toString('base64')}`
  } catch {
    return null
  }
}

/** Заголовок → основная часть и последние слова для плашки */
function splitTitle(title: string): { main: string; tail: string } {
  const words = title.split(/\s+/).filter(Boolean)
  if (words.length < 4) return { main: title, tail: '' }
  const tail: string[] = []
  while (words.length > 2 && (tail.join(' ').length < 14 || tail.length < 2) && tail.length < 4) {
    tail.unshift(words.pop()!)
  }
  return { main: words.join(' '), tail: tail.join(' ') }
}

function titleSize(n: number) {
  return n <= 45 ? 70 : n <= 70 ? 62 : n <= 95 ? 54 : n <= 120 ? 48 : 42
}

/** Подпись к фото: автор/лицензия без ссылки, коротко */
function photoCredit(credit: string | null | undefined): string {
  const c = (credit || '').split(' — ')[0].replace(/\s+/g, ' ').trim()
  return c.length > 52 ? `${c.slice(0, 49)}…` : c
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const article = await articleBySlug((await params).slug)
  if (!article) return new Response('Not found', { status: 404 })

  const { ink, sky } = COVER_THEME
  const img = asMedia(article.coverImage)
  const photo = await photoDataUrl(img?.url || img?.sizes?.hero?.url)
  const raw = article.title.length > 140 ? `${article.title.slice(0, 137)}…` : article.title
  const upper = raw.toLocaleUpperCase('kk-KZ')
  const { main, tail } = splitTitle(upper)
  const size = titleSize(upper.length)
  const credit = photoCredit(img?.credit)
  const creditLine = credit ? `Фото: ${credit}` : ''
  const host = SITE.url.replace(/^https?:\/\//, '')
  const allText = `${upper}${creditLine}${host}0123456789·…`

  const [black, regular, logo] = await Promise.all([
    loadFont('Inter', 900, allText), loadFont('Inter', 500, allText), loadFont('Space Grotesk', 700, 'TechTalQ'),
  ])
  const fonts = [
    black && { name: 'Inter', data: black, weight: 900 as const, style: 'normal' as const },
    regular && { name: 'Inter', data: regular, weight: 500 as const, style: 'normal' as const },
    logo && { name: 'Space Grotesk', data: logo, weight: 700 as const, style: 'normal' as const },
  ].filter(Boolean) as { name: string; data: ArrayBuffer; weight: 900 | 700 | 500; style: 'normal' }[]

  const png = new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', position: 'relative', backgroundColor: ink,
        color: '#fff', fontFamily: 'Inter' }}>
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photo} width={W} height={H} style={{ position: 'absolute', left: 0, top: 0, width: W, height: H }} alt="" />
        ) : (
          <div style={{ position: 'absolute', right: -200, top: 120, width: 760, height: 760, borderRadius: 9999,
            border: `120px solid ${sky}22`, display: 'flex' }} />
        )}

        {/* затемнение сверху под логотип и снизу под заголовок */}
        <div style={{ position: 'absolute', left: 0, top: 0, width: W, height: 260, display: 'flex',
          backgroundImage: 'linear-gradient(to bottom, rgba(11,27,58,0.7), rgba(11,27,58,0))' }} />
        <div style={{ position: 'absolute', left: 0, bottom: 0, width: W, height: 820, display: 'flex',
          backgroundImage: 'linear-gradient(to bottom, rgba(11,27,58,0) 0%, rgba(11,27,58,0.82) 42%, rgba(11,27,58,0.97) 70%, #0B1B3A 100%)' }} />

        {/* логотип по центру сверху, бирюзовая черта под ним */}
        <div style={{ position: 'absolute', top: 66, left: 0, width: W, display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <svg width="40" height="40" viewBox="0 0 64 64" fill="none">
              <circle cx="27" cy="27" r="20" stroke="#fff" strokeWidth="9" />
              <circle cx="27" cy="27" r="4.2" fill={sky} />
              <path d="M39.5 39.5l15 15" stroke={COVER_THEME.gold} strokeWidth="8" strokeLinecap="round" />
            </svg>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 38, fontWeight: 700, display: 'flex' }}>
              <span>TechTal</span><span style={{ color: sky, marginLeft: -9 }}>Q</span>{/* рендерер даёт лишний зазор после «l» */}
            </div>
          </div>
          <div style={{ width: 200, height: 6, borderRadius: 3, backgroundColor: sky, display: 'flex' }} />
        </div>

        {/* заголовок */}
        <div style={{ position: 'absolute', left: 0, bottom: creditLine ? 118 : 96, width: W, display: 'flex',
          flexDirection: 'column' }}>
          <div style={{ display: 'flex', marginLeft: PAD, marginRight: PAD - 10, paddingLeft: 26,
            borderLeft: `9px solid ${sky}` }}>
            <div style={{ fontSize: size, fontWeight: 900, lineHeight: 1.06, letterSpacing: -1, display: 'flex' }}>
              {main}
            </div>
          </div>
          {tail && (
            <div style={{ display: 'flex', marginTop: 6, paddingLeft: PAD, paddingRight: 120, paddingTop: 4, paddingBottom: 8,
              backgroundImage: `linear-gradient(to right, ${sky} 0%, rgba(0,175,202,0.92) 55%, rgba(0,175,202,0) 100%)` }}>
              <div style={{ fontSize: size, fontWeight: 900, lineHeight: 1.06, letterSpacing: -1, display: 'flex' }}>
                {tail}
              </div>
            </div>
          )}
        </div>

        {/* подпись к фото и адрес сайта */}
        <div style={{ position: 'absolute', left: PAD, right: PAD, bottom: 52, display: 'flex',
          justifyContent: 'space-between', fontSize: 24, fontWeight: 500, color: 'rgba(255,255,255,0.55)' }}>
          <div style={{ display: 'flex' }}>{creditLine}</div>
          <div style={{ display: 'flex' }}>{host}</div>
        </div>
      </div>
    ),
    { width: W, height: H, fonts: fonts.length ? fonts : undefined },
  )

  const jpg = await sharp(Buffer.from(await png.arrayBuffer())).jpeg({ quality: 90, mozjpeg: true }).toBuffer()
  return new Response(new Uint8Array(jpg), {
    headers: {
      'Content-Type': 'image/jpeg',
      'Cache-Control': 'public, max-age=31536000, s-maxage=31536000, immutable',
    },
  })
}
