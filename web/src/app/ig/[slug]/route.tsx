import { ImageResponse } from 'next/og'
import sharp from 'sharp'
import { articleBySlug } from '@/lib/cms'
import { COVER_THEME } from '@/lib/cover'
import { loadFont } from '@/lib/ogFonts'
import { SITE } from '@/lib/site'
import { asCategory, asMedia } from '@/lib/types'

// Картинка для поста в Instagram: 1080×1350 (4:5), JPEG — PNG и WebP Instagram API не принимает.
// ?format=story — сторис 1080×1920: те же элементы, отступы под шапку и поле ответа Instagram.
// Фото на весь кадр, логотип в углу, снизу затемнение: метка рубрики, заголовок (последние слова — бирюзовым),
// тонкая линия и подпись к фото. Цвета и шрифты — брендбук TechTalQ.
const W = 1080
const POST_H = 1350
const STORY_H = 1920
const PAD = 72

/** Фото статьи → JPEG data URL на весь кадр (Satori не читает WebP) */
async function photoDataUrl(src: string | null | undefined, H: number): Promise<string | null> {
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
  return n <= 45 ? 64 : n <= 70 ? 58 : n <= 95 ? 52 : n <= 120 ? 47 : 43
}

/** Подпись к фото: автор/лицензия без ссылки, коротко */
function photoCredit(credit: string | null | undefined): string {
  const c = (credit || '').split(' — ')[0].replace(/\s+/g, ' ').replace(/^(Сурет|Фото|Photo)\s*:\s*/i, '').trim()
  return c.length > 52 ? `${c.slice(0, 49)}…` : c
}

export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const story = new URL(req.url).searchParams.get('format') === 'story'
  const H = story ? STORY_H : POST_H
  const article = await articleBySlug((await params).slug)
  if (!article) return new Response('Not found', { status: 404 })

  const { ink, sky } = COVER_THEME
  const img = asMedia(article.coverImage)
  const photo = await photoDataUrl(img?.url || img?.sizes?.hero?.url, H)
  const raw = article.title.length > 140 ? `${article.title.slice(0, 137)}…` : article.title
  const { main, tail } = splitTitle(raw)
  const size = titleSize(raw.length)
  const label = (asCategory(article.category)?.name || 'Технология').toLocaleUpperCase('kk-KZ')
  const credit = photoCredit(img?.credit)
  const creditLine = credit ? `Фото: ${credit}` : ''
  const host = SITE.url.replace(/^https?:\/\//, '')
  const footer = story ? `Толығы — ${host}` : host
  const allText = `${raw}${label}${creditLine}${footer}0123456789·…`

  const [black, regular, logo] = await Promise.all([
    loadFont('Inter', 800, allText), loadFont('Inter', 500, allText), loadFont('Space Grotesk', 700, 'TechTalQ'),
  ])
  const fonts = [
    black && { name: 'Inter', data: black, weight: 800 as const, style: 'normal' as const },
    regular && { name: 'Inter', data: regular, weight: 500 as const, style: 'normal' as const },
    logo && { name: 'Space Grotesk', data: logo, weight: 700 as const, style: 'normal' as const },
  ].filter(Boolean) as { name: string; data: ArrayBuffer; weight: 800 | 700 | 500; style: 'normal' }[]

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
        <div style={{ position: 'absolute', left: 0, top: 0, width: W, height: story ? 480 : 300, display: 'flex',
          backgroundImage: 'linear-gradient(to bottom, rgba(11,27,58,0.9) 0%, rgba(11,27,58,0.6) 45%, rgba(11,27,58,0) 100%)' }} />
        <div style={{ position: 'absolute', left: 0, bottom: 0, width: W, height: story ? 1100 : 820, display: 'flex',
          backgroundImage: 'linear-gradient(to bottom, rgba(11,27,58,0) 0%, rgba(11,27,58,0.82) 42%, rgba(11,27,58,0.97) 70%, #0B1B3A 100%)' }} />

        {/* логотип в левом верхнем углу */}
        <div style={{ position: 'absolute', top: story ? 210 : 60, left: PAD, display: 'flex', alignItems: 'center', gap: 12 }}>
          <svg width="38" height="38" viewBox="0 0 64 64" fill="none">
            <circle cx="27" cy="27" r="20" stroke="#fff" strokeWidth="9" />
            <circle cx="27" cy="27" r="4.2" fill={sky} />
            <path d="M39.5 39.5l15 15" stroke={COVER_THEME.gold} strokeWidth="8" strokeLinecap="round" />
          </svg>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 34, fontWeight: 700, display: 'flex' }}>
            <span>TechTal</span><span style={{ color: sky, marginLeft: -8 }}>Q</span>{/* рендерер даёт лишний зазор после «l» */}
          </div>
        </div>

        {/* рубрика, заголовок, линия и подпись */}
        <div style={{ position: 'absolute', left: PAD, right: PAD, bottom: story ? 300 : 56, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex' }}>
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 2.5, padding: '9px 16px', borderRadius: 8,
              backgroundColor: sky, color: ink, display: 'flex' }}>
              {label}
            </div>
          </div>
          <div style={{ fontSize: size, fontWeight: 800, lineHeight: 1.12, letterSpacing: -1, marginTop: 26,
            display: 'flex', flexWrap: 'wrap' }}>
            {[...main.split(' ').map((w) => ({ w, hi: false })), ...(tail ? tail.split(' ') : []).map((w) => ({ w, hi: true }))].map(
              ({ w, hi }, i) => <span key={i} style={{ marginRight: size * 0.24, color: hi ? sky : '#fff' }}>{w}</span>,
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', marginTop: 34, gap: 18 }}>
            <div style={{ width: 64, height: 6, borderRadius: 3, backgroundColor: COVER_THEME.gold, display: 'flex' }} />
            <div style={{ flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.22)', display: 'flex' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20, fontSize: 23, fontWeight: 500,
            color: 'rgba(255,255,255,0.6)' }}>
            <div style={{ display: 'flex' }}>{creditLine}</div>
            <div style={{ display: 'flex', color: story ? COVER_THEME.gold : undefined }}>{footer}</div>
          </div>
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
