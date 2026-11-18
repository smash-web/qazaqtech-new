import { NextResponse } from 'next/server'
import { getCMS } from '@/lib/cms'
import { hasRole } from '@/access'
import { IG_SETTINGS, graph, igRedirectUri, readState } from '@/lib/instagram'
import { SITE } from '@/lib/site'

export const dynamic = 'force-dynamic'
const BACK = `${SITE.url}/admin/globals/instagram-settings`
const fail = (msg: string) => NextResponse.redirect(`${BACK}?ig_error=${encodeURIComponent(msg)}`)

/** Шаг 2: Meta вернула код — меняем его на токен, находим аккаунт Instagram и сохраняем в настройках */
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams
  if (q.get('error') || q.get('error_reason')) {
    return fail(`Meta: подключение отменено (${q.get('error_description') || q.get('error_reason') || q.get('error')})`)
  }
  const payload = await getCMS()
  const { user } = await payload.auth({ headers: req.headers })
  const uid = readState(q.get('state'))
  if (!user || !hasRole(user as never, 'developer') || !uid || String(user.id) !== uid) {
    return fail('Подключение не подтверждено: войдите в админку как разработчик и нажмите «Подключить» ещё раз.')
  }
  const code = q.get('code') || ''
  if (!code) return fail('Meta не вернула код подключения.')

  const appId = process.env.META_APP_ID || ''
  const secret = process.env.META_APP_SECRET || ''
  try {
    const tok = await graph('oauth/access_token', { client_id: appId, client_secret: secret, redirect_uri: igRedirectUri(), code })
    const token = String(tok.access_token || '')
    if (!token) throw new Error('Meta не выдала токен')

    // Срок жизни: у токена системного пользователя expires_at = 0 (бессрочный)
    let expiresAt: string | null = null
    try {
      const dbg = await graph('debug_token', { input_token: token, access_token: `${appId}|${secret}` })
      const exp = Number((dbg.data as { expires_at?: number } | undefined)?.expires_at || 0)
      if (exp > 0) expiresAt = new Date(exp * 1000).toISOString()
    } catch { /* срок не критичен */ }

    const acc = await graph('me/assigned_instagram_accounts', { fields: 'id,username', access_token: token })
    const list = (acc.data as { id: string; username?: string }[] | undefined) || []
    if (!list.length) throw new Error('В доступе нет ни одного аккаунта Instagram — при входе выберите аккаунт канала.')
    const ig = list[0]

    const now = new Date().toISOString()
    await payload.updateGlobal({
      slug: IG_SETTINGS,
      overrideAccess: true,
      data: {
        username: ig.username || '',
        igUserId: String(ig.id),
        accessToken: token,
        tokenUpdatedAt: now,
        tokenExpiresAt: expiresAt,
        lastError: list.length > 1 ? `Доступно аккаунтов: ${list.length}; выбран @${ig.username}.` : '',
      },
    } as never)
  } catch (e) {
    return fail(e instanceof Error ? e.message.slice(0, 300) : 'Не удалось подключить Instagram.')
  }
  return NextResponse.redirect(`${BACK}?ig=connected`)
}
