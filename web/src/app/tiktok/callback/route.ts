import { NextResponse } from 'next/server'
import { getCMS } from '@/lib/cms'
import { hasRole } from '@/access'
import { readState } from '@/lib/instagram'
import { TT_SETTINGS, ttJson, ttRedirectUri } from '@/lib/tiktok'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'
const BACK = `${SITE.url}/admin/globals/tiktok-settings`
const fail = (msg: string) => NextResponse.redirect(`${BACK}?tt_error=${encodeURIComponent(msg)}`)

/** Шаг 2: TikTok вернул код — меняем на токены (access 24 ч, refresh 365 дней) и сохраняем */
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams
  if (q.get('error')) return fail(`TikTok: подключение отменено (${q.get('error_description') || q.get('error')})`)
  const payload = await getCMS()
  // Кто начал подключение — из подписанного state (на cookie не полагаемся)
  const uid = readState(q.get('state'))
  if (!uid) return fail('Ссылка подключения устарела (действует 15 минут) — нажмите «Подключить TikTok» ещё раз.')
  const starter = await payload.findByID({ collection: 'users', id: uid, overrideAccess: true, depth: 0 }).catch(() => null)
  if (!starter || !hasRole(starter as never, 'developer')) return fail('Подключать TikTok может только разработчик.')
  const code = q.get('code') || ''
  if (!code) return fail('TikTok не вернул код подключения.')

  try {
    const tok = await ttJson(await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_key: process.env.TIKTOK_CLIENT_KEY || '',
        client_secret: process.env.TIKTOK_CLIENT_SECRET || '',
        code,
        grant_type: 'authorization_code',
        redirect_uri: ttRedirectUri(),
      }),
    }))
    const scope = String(tok.scope || '')
    if (scope && !scope.includes('video.upload')) throw new Error('Не выдано разрешение на загрузку — при входе разрешите все пункты.')
    const access = String(tok.access_token || '')
    if (!access) throw new Error('TikTok не выдал токен')

    let displayName = ''
    try {
      const info = await ttJson(await fetch('https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name', {
        headers: { Authorization: `Bearer ${access}` },
      }))
      displayName = String(((info.data as { user?: { display_name?: string } })?.user?.display_name) || '')
    } catch { /* имя не критично */ }

    const now = Date.now()
    await payload.updateGlobal({
      slug: TT_SETTINGS,
      overrideAccess: true,
      data: {
        displayName: displayName || String(tok.open_id || ''),
        openId: String(tok.open_id || ''),
        accessToken: access,
        refreshToken: String(tok.refresh_token || ''),
        accessExpiresAt: new Date(now + Number(tok.expires_in || 86400) * 1000).toISOString(),
        refreshExpiresAt: new Date(now + Number(tok.refresh_expires_in || 31536000) * 1000).toISOString(),
        lastError: '',
      },
    } as never)
  } catch (e) {
    return fail(e instanceof Error ? e.message.slice(0, 300) : 'Не удалось подключить TikTok.')
  }
  return NextResponse.redirect(`${BACK}?tt=connected`)
}
