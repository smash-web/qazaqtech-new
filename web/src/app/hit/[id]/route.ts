import config from '@payload-config'
import { getPayload } from 'payload'

export const dynamic = 'force-dynamic'

const SCHEMA = (process.env.PAYLOAD_DB_SCHEMA || 'public').replace(/[^a-z0-9_]/gi, '')

/** Счётчик просмотров: +1 к статье. Прямой SQL — чтобы не трогать updatedAt и не сбрасывать кэш сайта. */
export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  if (!/^\d{1,9}$/.test(id)) return Response.json({ error: 'bad id' }, { status: 400 })
  const payload = await getPayload({ config })
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pool = (payload.db as any).pool
  const res = await pool.query(
    `update "${SCHEMA}"."articles" set views = coalesce(views, 0) + 1 where id = $1 and status = 'published' returning views`,
    [Number(id)],
  )
  if (!res.rows.length) return Response.json({ error: 'not found' }, { status: 404 })
  return Response.json({ views: Number(res.rows[0].views) }, { headers: { 'Cache-Control': 'no-store' } })
}
