import { NextResponse } from 'next/server'
import { getCMS } from '@/lib/cms'
import { hasRole } from '@/access'
import { IG_SCOPES, igAppConfigured, igRedirectUri, makeState } from '@/lib/instagram'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'
const BACK = `${SITE.url}/admin/globals/instagram-settings`

/** Шаг 1: отправляем разработчика на страницу входа Instagram */
export async function GET(req: Request) {
  const payload = await getCMS()
  const { user } = await payload.auth({ headers: req.headers })
  if (!user || !hasRole(user as never, 'developer')) return NextResponse.redirect(`${SITE.url}/admin`)
  if (!igAppConfigured()) {
    const msg = 'На сервере не заданы INSTAGRAM_APP_ID и INSTAGRAM_APP_SECRET — сначала создайте приложение Meta.'
    return NextResponse.redirect(`${BACK}?ig_error=${encodeURIComponent(msg)}`)
  }
  const url = new URL('https://www.instagram.com/oauth/authorize')
  url.searchParams.set('client_id', process.env.INSTAGRAM_APP_ID!)
  url.searchParams.set('redirect_uri', igRedirectUri())
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', IG_SCOPES)
  url.searchParams.set('state', makeState(user.id))
  return NextResponse.redirect(url.toString())
}
