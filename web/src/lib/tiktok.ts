import 'server-only'
import { SITE } from './site'

/** TikTok Content Posting API: вход Login Kit (OAuth v2), черновики фото (MEDIA_UPLOAD). */
export const TT_SETTINGS = 'tiktok-settings'
export const TT_SCOPES = 'user.info.basic,video.upload'
export const ttRedirectUri = () => `${SITE.url}/tiktok/callback`
export const ttConfigured = () => Boolean(process.env.TIKTOK_CLIENT_KEY && process.env.TIKTOK_CLIENT_SECRET)

/** Ответ TikTok API → JSON; ошибку превращаем в короткий текст для админки */
export async function ttJson(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text()
  let data: Record<string, unknown> = {}
  try { data = JSON.parse(text) } catch { /* не JSON */ }
  const err = data.error as { code?: string; message?: string } | string | undefined
  const failed = !res.ok || (typeof err === 'object' && err?.code && err.code !== 'ok') || (typeof err === 'string' && err)
  if (failed) {
    const msg = (typeof err === 'object' && (err?.message || err?.code)) || (data.error_description as string) || (typeof err === 'string' ? err : '') || text.slice(0, 200)
    throw new Error(`TikTok: ${msg}`)
  }
  return data
}
