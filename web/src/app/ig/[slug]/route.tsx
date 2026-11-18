import { ImageResponse } from 'next/og'
import sharp from 'sharp'
import { articleBySlug } from '@/lib/cms'
import { COVER_THEME } from '@/lib/cover'
import { loadFont } from '@/lib/ogFonts'
import { SITE } from '@/lib/site'
import { asCategory, asMedia } from '@/lib/types'

// Картинка для поста в Instagram: 1080×1350 (4:5), JPEG — PNG и WebP Instagram API не принимает.
// Сверху фото статьи, снизу тёмная плашка брендбука с рубрикой, заголовком и логотипом.
const W = 1080
const H = 1350
const PHOTO_H = 740

function titleSize(title: string, roomy: boolean) {
  const n = title.length
  const base = n <= 60 ? 62 : n <= 90 ? 54 : n <= 120 ? 48 : 42
  return roomy ? base + 10 : base
}

/** Фото статьи → JPEG data URL нужного размера (Satori не читает WebP) */
async function photoDataUrl(src: string | null | undefined): Promise<string | null> {
  if (!src) return null
  try {
    const url = src.startsWith('http') ? src : `${SITE.url}${src}`
    const res = await fetch(url)
    if (!res.ok) return null
    const jpg = await sharp(Buffer.from(await res.arrayBuffer()))
      .resize(W, PHOTO_H, { fit: 'cover', position: 'attention' })
      .jpeg({ quality: 88 })
      .toBuffer()
    return `data:image/jpeg;base64,${jpg.toString('base64')}`
  } catch {
    return null
  }
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const article = await articleBySlug((await params).slug)
  if (!article) return new Response('Not found', { status: 404 })

  const { ink, sky, gold } = COVER_THEME
  const cat = asCategory(article.category)
  const img = asMedia(article.coverImage)
  const photo = await photoDataUrl(img?.sizes?.hero?.url || img?.url)
  const title = article.title.length > 150 ? `${article.title.slice(0, 147)}…` : article.title
  const label = (cat?.name || 'Технология').toUpperCase()
  const host = SITE.url.replace(/^https?:\/\//, '')
  const allText = `${label}${title}${host}0123456789·…`

  const [bold, regular, logo] = await Promise.all([
    loadFont('Inter', 800, allText), loadFont('Inter', 500, allText), loadFont('Space Grotesk', 700, 'TechTalQ'),
  ])
  const fonts = [
    bold && { name: 'Inter', data: bold, weight: 800 as const, style: 'normal' as const },
    regular && { name: 'Inter', data: regular, weight: 500 as const, style: 'normal' as const },
    logo && { name: 'Space Grotesk', data: logo, weight: 700 as const, style: 'normal' as const },
  ].filter(Boolean) as { name: string; data: ArrayBuffer; weight: 800 | 700 | 500; style: 'normal' }[]

  const png = new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', backgroundColor: ink,
        color: '#fff', fontFamily: 'Inter', position: 'relative' }}>
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photo} width={W} height={PHOTO_H} style={{ width: W, height: PHOTO_H, objectFit: 'cover' }} alt="" />
        ) : (
          <div style={{ position: 'absolute', right: -170, top: -190, width: 640, height: 640, borderRadius: 9999,
            border: `100px solid ${sky}24`, display: 'flex' }} />
        )}

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: photo ? 'space-between' : 'flex-end',
          padding: photo ? '40px 72px 56px' : '72px 72px 56px', gap: 28 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={{ display: 'flex' }}>
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 2.5, padding: '9px 16px', borderRadius: 8,
                backgroundColor: sky, color: ink, display: 'flex' }}>
                {label}
              </div>
            </div>
            <div style={{ fontSize: titleSize(title, !photo), fontWeight: 800, lineHeight: 1.14, letterSpacing: -1.2,
              display: 'flex' }}>
              {title}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: photo ? 0 : 56 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <svg width="46" height="46" viewBox="0 0 64 64" fill="none">
                <circle cx="27" cy="27" r="20" stroke="#fff" strokeWidth="9" />
                <circle cx="27" cy="27" r="4.2" fill={sky} />
                <path d="M39.5 39.5l15 15" stroke={gold} strokeWidth="8" strokeLinecap="round" />
              </svg>
              <div style={{ fontFamily: 'Space Grotesk', fontSize: 36, fontWeight: 700, letterSpacing: -1, display: 'flex' }}>
                <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700 }}>TechTal</span><span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, color: sky }}>Q</span>
              </div>
            </div>
            <div style={{ fontSize: 26, fontWeight: 500, color: '#9FB0CC', display: 'flex' }}>{host}</div>
          </div>
        </div>
        <div style={{ position: 'absolute', left: 72, bottom: 0, width: 120, height: 10, backgroundColor: gold, display: 'flex' }} />
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
