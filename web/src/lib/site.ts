export const SITE = {
  name: process.env.NEXT_PUBLIC_SITE_NAME || 'QazaqTech',
  tagline: 'Әлемдік технология жаңалықтары қазақ тілінде',
  url: (process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000').replace(/\/$/, ''),
  locale: 'kk_KZ',
}

const MONTHS = ['қаңтар', 'ақпан', 'наурыз', 'сәуір', 'мамыр', 'маусым', 'шілде', 'тамыз', 'қыркүйек', 'қазан', 'қараша', 'желтоқсан']

/** «10 қараша 2026, 14:05» — без зависимости от ICU-данных сервера */
export function formatDate(iso?: string | null, withTime = true): string {
  if (!iso) return ''
  const d = new Date(new Date(iso).getTime() + 5 * 3600 * 1000) // Asia/Almaty, UTC+5
  const date = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
  if (!withTime) return date
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mm = String(d.getUTCMinutes()).padStart(2, '0')
  return `${date}, ${hh}:${mm}`
}
