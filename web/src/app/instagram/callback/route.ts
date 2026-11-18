import { NextResponse } from 'next/server'
import { getCMS } from '@/lib/cms'
import { hasRole } from '@/access'
import { IG_SETTINGS, igJson, igRedirectUri, readState } from '@/lib/instagram'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'
const BACK = `${SITE.url}/admin/globals/instagram-settings`
const fail = (msg: string) => NextResponse.redirect(`${BACK}?ig_error=${encodeURIComponent(msg)}`)

/** Шаг 2: Instagram вернул код — меняем его на долгий токен (60 дней) и сохраняем в настройках */
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams
  if (q.get('error')) return fail(`Instagram отказал: ${q.get('error_description') || q.get('error')}`)

  const payload = await getCMS()
  const { user } = await payload.auth({ headers: req.headers })
  const uid = readState(q.get('state'))
  if (!user || !hasRole(user as never, 'developer') || !uid || String(user.id) !== uid) {
    return fail('Подключение не подтверждено: войдите в админку как разработчик и нажмите «Подключить» ещё раз.')
  }
  const code = (q.get('code') || '').replace(/#_$/, '')
  if (!code) return fail('Instagram не вернул код подключения.')

  try {
    const form = new URLSearchParams({
      client_id: process.env.INSTAGRAM_APP_ID || '',
      client_secret: process.env.INSTAGRAM_APP_SECRET || '',
      grant_type: 'authorization_code',
      redirect_uri: igRedirectUri(),
      code,
    })
    const short = await igJson(await fetch('https://api.instagram.com/oauth/access_token', { method: 'POST', body: form }))
    const first = (Array.isArray(short.data) ? short.data[0] : short) as { access_token?: string; permissions?: string | string[] }
    if (!first?.access_token) throw new Error('Instagram не выдал токен')
    const perms = Array.isArray(first.permissions) ? first.permissions.join(',') : String(first.permissions || '')
    if (perms && !perms.includes('instagram_business_content_publish')) {
      throw new Error('Не выдано разрешение на публикацию — при входе отметьте все галочки.')
    }

    const longUrl = new URL('https://graph.instagram.com/access_token')
    longUrl.searchParams.set('grant_type', 'ig_exchange_token')
    longUrl.searchParams.set('client_secret', process.env.INSTAGRAM_APP_SECRET || '')
    longUrl.searchParams.set('access_token', first.access_token)
    const long = await igJson(await fetch(longUrl))
    const token = String(long.access_token || '')
    const expiresIn = Number(long.expires_in || 60 * 24 * 3600)

    const meUrl = new URL('https://graph.instagram.com/me')
    meUrl.searchParams.set('fields', 'user_id,username,account_type')
    meUrl.searchParams.set('access_token', token)
    const me = await igJson(await fetch(meUrl))

    const now = new Date()
    await payload.updateGlobal({
      slug: IG_SETTINGS,
      overrideAccess: true,
      data: {
        username: String(me.username || ''),
        igUserId: String(me.user_id || me.id || ''),
        accessToken: token,
        tokenUpdatedAt: now.toISOString(),
        tokenExpiresAt: new Date(now.getTime() + expiresIn * 1000).toISOString(),
        lastError: '',
      },
    } as never)
  } catch (e) {
    return fail(e instanceof Error ? e.message.slice(0, 300) : 'Не удалось подключить Instagram.')
  }
  return NextResponse.redirect(`${BACK}?ig=connected`)
}
