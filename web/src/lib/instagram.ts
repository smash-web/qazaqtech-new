import 'server-only'
import crypto from 'crypto'
import { SITE } from './site'

/**
 * Instagram API with Unified Login (с конца 2026 года — единственный вариант для новых приложений Meta):
 * вход через диалог Facebook Login for Business с config_id, токен — системного пользователя бизнес-портфолио
 * (обычно бессрочный), все вызовы — graph.facebook.com.
 */
export const GRAPH_VERSION = process.env.META_GRAPH_VERSION || 'v26.0'
export const GRAPH = `https://graph.facebook.com/${GRAPH_VERSION}`
export const IG_SETTINGS = 'instagram-settings'
export const igRedirectUri = () => `${SITE.url}/instagram/callback`
export const igAppConfigured = () =>
  Boolean(process.env.META_APP_ID && process.env.META_APP_SECRET && process.env.META_CONFIG_ID)

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

/** Ответ Graph API → JSON; ошибку превращаем в короткий текст для админки */
export async function graphJson(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text()
  let data: Record<string, unknown> = {}
  try { data = JSON.parse(text) } catch { /* не JSON */ }
  if (!res.ok || data.error) {
    const err = data.error as { message?: string; error_user_msg?: string } | string | undefined
    const msg = (typeof err === 'object' && (err?.error_user_msg || err?.message)) || (typeof err === 'string' ? err : '') || text.slice(0, 200)
    throw new Error(`Meta: ${msg}`)
  }
  return data
}

export const graph = (path: string, params: Record<string, string>) => {
  const url = new URL(`${GRAPH}/${path.replace(/^\//, '')}`)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  return fetch(url, { cache: 'no-store' }).then(graphJson)
}
