import { NextResponse } from 'next/server'
import { getCMS } from '@/lib/cms'
import { hasRole } from '@/access'
import { makeState } from '@/lib/instagram'
import { TT_SCOPES, ttConfigured, ttRedirectUri } from '@/lib/tiktok'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'
const BACK = `${SITE.url}/admin/globals/tiktok-settings`

/** Шаг 1: отправляем разработчика на страницу входа TikTok */
export async function GET(req: Request) {
  const payload = await getCMS()
  const { user } = await payload.auth({ headers: req.headers })
  if (!user || !hasRole(user as never, 'developer')) return NextResponse.redirect(`${SITE.url}/admin`)
  if (!ttConfigured()) {
    const msg = 'На сервере не заданы TIKTOK_CLIENT_KEY и TIKTOK_CLIENT_SECRET — сначала настройте приложение TikTok.'
    return NextResponse.redirect(`${BACK}?tt_error=${encodeURIComponent(msg)}`)
  }
  const url = new URL('https://www.tiktok.com/v2/auth/authorize/')
  url.searchParams.set('client_key', process.env.TIKTOK_CLIENT_KEY!)
  url.searchParams.set('scope', TT_SCOPES)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('redirect_uri', ttRedirectUri())
  url.searchParams.set('state', makeState(user.id))
  return NextResponse.redirect(url.toString())
}
