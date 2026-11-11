import config from '@payload-config'
import { getPayload } from 'payload'

export const dynamic = 'force-dynamic'

const SCHEMA = (process.env.PAYLOAD_DB_SCHEMA || 'public').replace(/[^a-z0-9_]/gi, '')

/** Свежие счётчики просмотров для карточек: GET /hit?ids=1,2,3 → { "1": 10, "2": 0 } (мимо кэша страниц). */
export async function GET(req: Request) {
  const ids = (new URL(req.url).searchParams.get('ids') || '')
    .split(',').filter((x) => /^\d{1,9}$/.test(x)).slice(0, 100).map(Number)
  if (!ids.length) return Response.json({})
  const payload = await getPayload({ config })
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pool = (payload.db as any).pool
  const res = await pool.query(
    `select id, coalesce(views, 0) as views from "${SCHEMA}"."articles" where id = any($1::int[]) and status = 'published'`,
    [ids],
  )
  const out: Record<string, number> = {}
  for (const r of res.rows) out[String(r.id)] = Number(r.views)
  return Response.json(out, { headers: { 'Cache-Control': 'no-store' } })
}
