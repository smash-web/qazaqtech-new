import path from 'path'
import { fileURLToPath } from 'url'
import { buildConfig } from 'payload'
import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import { en } from '@payloadcms/translations/languages/en'
import { ru } from '@payloadcms/translations/languages/ru'
import sharp from 'sharp'

import { Articles } from './collections/Articles'
import { Categories, Glossary, Media, Sources } from './collections/Taxonomy'
import { Users } from './collections/Users'
import { PipelineSettings } from './globals/PipelineSettings'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)
const siteURL = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'

export default buildConfig({
  serverURL: siteURL,
  admin: {
    user: Users.slug,
    meta: { titleSuffix: ' — Редакция' },
    importMap: { baseDir: path.resolve(dirname) },
  },
  collections: [Articles, Categories, Media, Sources, Glossary, Users],
  globals: [PipelineSettings],
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI || '', max: Number(process.env.DB_POOL_MAX || 5) },
    // Отдельная схема: таблицы CMS не видны через публичный REST API Supabase
    schemaName: process.env.PAYLOAD_DB_SCHEMA || 'public',
    // В dev схема синхронизируется автоматически; в проде — только миграции (npm run payload migrate)
    push: process.env.NODE_ENV !== 'production',
  }),
  i18n: { supportedLanguages: { ru, en }, fallbackLanguage: 'ru' },
  typescript: { outputFile: path.resolve(dirname, 'payload-types.ts') },
  cors: [siteURL],
  csrf: [siteURL],
  sharp,
})
