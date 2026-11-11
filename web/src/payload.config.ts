import path from 'path'
import { fileURLToPath } from 'url'
import { buildConfig } from 'payload'
import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import { en } from '@payloadcms/translations/languages/en'
import { ru } from '@payloadcms/translations/languages/ru'
import { vercelBlobStorage } from '@payloadcms/storage-vercel-blob'
import sharp from 'sharp'

import { Articles } from './collections/Articles'
import { Pages } from './collections/Pages'
import { Categories, Glossary, Media, Sources } from './collections/Taxonomy'
import { Users } from './collections/Users'
import { PipelineSettings } from './globals/PipelineSettings'
import { SiteSettings } from './globals/SiteSettings'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)
const siteURL = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'

export default buildConfig({
  serverURL: siteURL,
  admin: {
    user: Users.slug,
    meta: { titleSuffix: ' — Редакция' },
    importMap: { baseDir: path.resolve(dirname) },
    components: {
      beforeDashboard: ['/components/admin/Dashboard#Dashboard'],
      graphics: { Logo: '/components/admin/Brand#Logo', Icon: '/components/admin/Brand#Icon' },
    },
  },
  collections: [Articles, Categories, Pages, Media, Sources, Glossary, Users],
  globals: [SiteSettings, PipelineSettings],
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI || '', max: Number(process.env.DB_POOL_MAX || 5) },
    // Отдельная схема: таблицы CMS не видны через публичный REST API Supabase
    schemaName: process.env.PAYLOAD_DB_SCHEMA || 'public',
    // В dev схема синхронизируется автоматически; в проде — только миграции (npm run payload migrate)
    push: process.env.NODE_ENV !== 'production',
  }),
  plugins: [
    // Медиафайлы — в Vercel Blob (файловая система Vercel только для чтения).
    // Без токена (локальная разработка, Docker) файлы сохраняются в папку media/.
    vercelBlobStorage({
      enabled: Boolean(process.env.BLOB_READ_WRITE_TOKEN),
      token: process.env.BLOB_READ_WRITE_TOKEN || '',
      collections: { media: true },
      clientUploads: true, // загрузка из браузера напрямую в Blob, минуя лимит 4.5 МБ функций
      addRandomSuffix: true,
    }),
  ],
  i18n: { supportedLanguages: { ru, en }, fallbackLanguage: 'ru' },
  typescript: { outputFile: path.resolve(dirname, 'payload-types.ts') },
  cors: [siteURL],
  csrf: [siteURL],
  sharp,
})
