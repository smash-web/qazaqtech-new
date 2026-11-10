/**
 * Начальное наполнение: рубрики, источники, глоссарий и пользователь-бот для конвейера.
 * Запуск: npm run seed   (повторный запуск безопасен — существующие записи не дублируются)
 */
import crypto from 'crypto'
import config from '@payload-config'
import { getPayload } from 'payload'

const CATEGORIES = [
  { slug: 'ai', name: 'Жасанды интеллект', order: 10 },
  { slug: 'big-tech', name: 'Ірі компаниялар', order: 20 },
  { slug: 'startups', name: 'Стартаптар мен инвестиция', order: 30 },
  { slug: 'security', name: 'Киберқауіпсіздік', order: 40 },
  { slug: 'gadgets', name: 'Гаджеттер', order: 50 },
  { slug: 'dev', name: 'Әзірлеу', order: 60 },
  { slug: 'science', name: 'Ғылым және ғарыш', order: 70 },
  { slug: 'policy', name: 'Реттеу және саясат', order: 80 },
]

// Топ мировых изданий с эксклюзивами и собственными репортажами.
// Адреса лент нужно проверить по логам первого сбора: недоступный источник пропускается с предупреждением.
// Reuters, Semafor и Axios Pro не дают публичных RSS — для них нужен лицензионный доступ.
// [название, сайт, лента, вес 1–10, активен]
const SOURCES: [string, string, string, number, boolean][] = [
  ['The Information', 'https://www.theinformation.com', 'https://www.theinformation.com/feed', 10, true],
  ['Bloomberg Technology', 'https://www.bloomberg.com/technology', 'https://feeds.bloomberg.com/technology/news.rss', 10, true],
  ['WSJ Technology', 'https://www.wsj.com/tech', 'https://feeds.a.dj.com/rss/RSSWSJD.xml', 9, true],
  ['Financial Times: Technology', 'https://www.ft.com/technology', 'https://www.ft.com/technology?format=rss', 9, true],
  ['The Verge', 'https://www.theverge.com', 'https://www.theverge.com/rss/index.xml', 9, true],
  ['CNBC Technology', 'https://www.cnbc.com/technology/', 'https://www.cnbc.com/id/19854910/device/rss/rss.html', 8, true],
  ['Business Insider: Tech', 'https://www.businessinsider.com/tech', 'https://feeds2.feedburner.com/businessinsider', 7, true],
  ['Platformer', 'https://www.platformer.news', 'https://www.platformer.news/rss/', 8, true],
  ['404 Media', 'https://www.404media.co', 'https://www.404media.co/rss/', 8, true],
  ['Wired', 'https://www.wired.com', 'https://www.wired.com/feed/rss', 8, true],
  ['Ars Technica', 'https://arstechnica.com', 'https://feeds.arstechnica.com/arstechnica/index', 8, true],
  ['MIT Technology Review', 'https://www.technologyreview.com', 'https://www.technologyreview.com/feed/', 8, true],
  ['VentureBeat', 'https://venturebeat.com', 'https://venturebeat.com/feed/', 7, true],
  ['SiliconANGLE', 'https://siliconangle.com', 'https://siliconangle.com/feed/', 7, true],
  ['Rest of World', 'https://restofworld.org', 'https://restofworld.org/feed/latest/', 7, true],
  ['Tech.eu', 'https://tech.eu', 'https://tech.eu/feed/', 6, true],
  ['Sifted', 'https://sifted.eu', 'https://sifted.eu/feed', 6, true],
  ['9to5Mac', 'https://9to5mac.com', 'https://9to5mac.com/feed/', 6, true],
  ['MacRumors', 'https://www.macrumors.com', 'https://feeds.macrumors.com/MacRumors-All', 6, true],
  // Общая лента (не только технологии) — включить после подключения ИИ-отбора
  ['Nikkei Asia', 'https://asia.nikkei.com/Business/Tech', 'https://asia.nikkei.com/rss/feed/nar', 7, false],
]

const GLOSSARY: { term: string; kk?: string; doNotTranslate?: boolean; note?: string }[] = [
  { term: 'artificial intelligence (AI)', kk: 'жасанды интеллект (ЖИ)' },
  { term: 'machine learning', kk: 'машиналық оқыту' },
  { term: 'neural network', kk: 'нейрондық желі' },
  { term: 'large language model (LLM)', kk: 'үлкен тілдік модель (LLM)' },
  { term: 'chatbot', kk: 'чат-бот' },
  { term: 'AI agent', kk: 'ЖИ-агент' },
  { term: 'training (of a model)', kk: 'модельді оқыту' },
  { term: 'dataset', kk: 'деректер жиыны' },
  { term: 'data center', kk: 'деректер орталығы' },
  { term: 'chip', kk: 'чип' },
  { term: 'semiconductor', kk: 'жартылай өткізгіш' },
  { term: 'GPU', kk: 'графикалық процессор (GPU)' },
  { term: 'cloud computing', kk: 'бұлтты есептеу' },
  { term: 'open source', kk: 'ашық бастапқы код' },
  { term: 'software', kk: 'бағдарламалық жасақтама' },
  { term: 'app / application', kk: 'қосымша' },
  { term: 'operating system', kk: 'операциялық жүйе' },
  { term: 'update', kk: 'жаңарту' },
  { term: 'user', kk: 'пайдаланушы' },
  { term: 'developer', kk: 'әзірлеуші' },
  { term: 'startup', kk: 'стартап' },
  { term: 'funding round', kk: 'инвестициялық раунд' },
  { term: 'valuation', kk: 'нарықтық бағасы', note: 'компанияның бағалануы' },
  { term: 'venture capital', kk: 'венчурлік капитал' },
  { term: 'cybersecurity', kk: 'киберқауіпсіздік' },
  { term: 'vulnerability', kk: 'осалдық' },
  { term: 'data breach / leak', kk: 'деректердің жылыстауы' },
  { term: 'ransomware', kk: 'бопсалаушы бағдарлама (ransomware)' },
  { term: 'encryption', kk: 'шифрлау' },
  { term: 'smartphone', kk: 'смартфон' },
  { term: 'quantum computer', kk: 'кванттық компьютер' },
  { term: 'iPhone', doNotTranslate: true },
  { term: 'Android', doNotTranslate: true },
  { term: 'Windows', doNotTranslate: true },
]

async function upsert(payload: Awaited<ReturnType<typeof getPayload>>, collection: 'categories' | 'sources' | 'glossary',
  key: string, value: string, data: Record<string, unknown>) {
  const found = await payload.find({ collection, where: { [key]: { equals: value } }, limit: 1, depth: 0 })
  if (found.docs.length) return false
  await payload.create({ collection, data: data as never })
  return true
}

async function seed() {
  const payload = await getPayload({ config })
  let n = 0
  for (const c of CATEGORIES) n += Number(await upsert(payload, 'categories', 'slug', c.slug, c))
  for (const [name, siteUrl, feedUrl, weight, active] of SOURCES)
    n += Number(await upsert(payload, 'sources', 'feedUrl', feedUrl, { name, siteUrl, feedUrl, weight, active }))
  for (const g of GLOSSARY) n += Number(await upsert(payload, 'glossary', 'term', g.term, g))
  payload.logger.info(`Добавлено записей: ${n}`)

  // Администратор (для первого входа) — из переменных ADMIN_EMAIL / ADMIN_PASSWORD
  const adminEmail = process.env.ADMIN_EMAIL
  if (adminEmail && process.env.ADMIN_PASSWORD) {
    const found = await payload.find({ collection: 'users', where: { email: { equals: adminEmail } }, limit: 1 })
    if (!found.docs.length) {
      await payload.create({
        collection: 'users',
        data: { email: adminEmail, name: 'Администратор', role: 'admin', password: process.env.ADMIN_PASSWORD } as never,
      })
      payload.logger.info(`Создан администратор ${adminEmail}`)
    }
  }

  // Бот конвейера — ключ API берётся из CMS_API_KEY (тот же секрет использует конвейер)
  const botEmail = process.env.PIPELINE_BOT_EMAIL || 'pipeline-bot@qazaqtech.local'
  const apiKey = process.env.CMS_API_KEY
  const bot = await payload.find({ collection: 'users', where: { email: { equals: botEmail } }, limit: 1 })
  if (!apiKey) {
    payload.logger.warn('CMS_API_KEY не задан — бот конвейера не создан')
  } else if (!bot.docs.length) {
    await payload.create({
      collection: 'users',
      data: {
        email: botEmail, name: 'Pipeline bot', role: 'bot',
        password: crypto.randomBytes(24).toString('base64url'), enableAPIKey: true, apiKey,
      } as never,
    })
    payload.logger.info('Создан бот конвейера')
  } else {
    await payload.update({ collection: 'users', id: bot.docs[0].id, data: { enableAPIKey: true, apiKey } as never })
    payload.logger.info('Ключ бота конвейера обновлён')
  }
  process.exit(0)
}

seed().catch((err) => {
  console.error(err)
  process.exit(1)
})
