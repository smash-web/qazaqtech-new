import 'server-only'
import crypto from 'crypto'
import { SITE } from './site'

export const IG_SCOPES = 'instagram_business_basic,instagram_business_content_publish'
export const IG_SETTINGS = 'instagram-settings'
export const igRedirectUri = () => `${SITE.url}/instagram/callback`
export const igAppConfigured = () => Boolean(process.env.INSTAGRAM_APP_ID && process.env.INSTAGRAM_APP_SECRET)

const sign = (v: string) =>
  crypto.createHmac('sha256', process.env.PAYLOAD_SECRET || '').update(`ig:${v}`).digest('base64url')

/** state для OAuth: кто начал подключение и когда; подпись — секретом Payload */
export function makeState(userId: string | number): string {
  const v = `${userId}.${Date.now()}`
  return `${v}.${sign(v)}`
}

export function readState(state: string | null): string | null {
  const parts = (state || '').split('.')
  if (parts.length !== 3) return null
  const [uid, ts, sig] = parts
  const expected = sign(`${uid}.${ts}`)
  if (sig.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return null
  if (Date.now() - Number(ts) > 15 * 60 * 1000) return null
  return uid
}

/** Ошибку Instagram API превращаем в короткий текст для админки */
export async function igJson(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text()
  let data: Record<string, unknown> = {}
  try { data = JSON.parse(text) } catch { /* не JSON */ }
  if (!res.ok || data.error || data.error_message) {
    const err = data.error as { message?: string } | string | undefined
    const msg = (typeof err === 'object' && err?.message) || (data.error_message as string) || (typeof err === 'string' ? err : '') || text.slice(0, 200)
    throw new Error(`Instagram: ${msg}`)
  }
  return data
}
