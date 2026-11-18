import { NextResponse } from 'next/server'
import { getCMS } from '@/lib/cms'
import { hasRole } from '@/access'
import { GRAPH_VERSION, igAppConfigured, igRedirectUri, makeState } from '@/lib/instagram'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'
const BACK = `${SITE.url}/admin/globals/instagram-settings`

/** Шаг 1: отправляем разработчика в диалог входа Meta (Unified Login: можно войти через Instagram) */
export async function GET(req: Request) {
  const payload = await getCMS()
  const { user } = await payload.auth({ headers: req.headers })
  if (!user || !hasRole(user as never, 'developer')) return NextResponse.redirect(`${SITE.url}/admin`)
  if (!igAppConfigured()) {
    const msg = 'На сервере не заданы META_APP_ID, META_APP_SECRET и META_CONFIG_ID — сначала настройте приложение Meta.'
    return NextResponse.redirect(`${BACK}?ig_error=${encodeURIComponent(msg)}`)
  }
  const url = new URL(`https://www.facebook.com/${GRAPH_VERSION}/dialog/oauth`)
  url.searchParams.set('client_id', process.env.META_APP_ID!)
  url.searchParams.set('config_id', process.env.META_CONFIG_ID!)
  url.searchParams.set('redirect_uri', igRedirectUri())
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('override_default_response_type', 'true')
  url.searchParams.set('state', makeState(user.id))
  return NextResponse.redirect(url.toString())
}
