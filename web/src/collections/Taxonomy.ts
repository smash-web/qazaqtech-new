import type { CollectionConfig } from 'payload'
import { anyone, isEditor, isStaff } from '../access'
import { revalidate } from '../lib/revalidate'
import { slugify } from '../lib/slugify'

export const Categories: CollectionConfig = {
  slug: 'categories',
  labels: { singular: 'Рубрика', plural: 'Рубрики' },
  admin: { useAsTitle: 'name', defaultColumns: ['name', 'slug', 'order'], group: 'Контент' },
  defaultSort: 'order',
  access: { read: anyone, create: isEditor, update: isEditor, delete: isEditor },
  hooks: {
    afterChange: [({ doc }) => (revalidate('categories', 'articles'), doc)],
    afterDelete: [({ doc }) => (revalidate('categories', 'articles'), doc)],
  },
  fields: [
    { name: 'name', label: 'Название (каз.)', type: 'text', required: true },
    {
      name: 'slug',
      type: 'text',
      required: true,
      unique: true,
      index: true,
      admin: { description: 'Латиницей; используется в URL и конвейером' },
      hooks: { beforeValidate: [({ value, data }) => slugify(String(value || data?.name || ''))] },
    },
    { name: 'description', label: 'Описание', type: 'textarea' },
    { name: 'order', label: 'Порядок в меню', type: 'number', defaultValue: 100 },
  ],
}

export const Sources: CollectionConfig = {
  slug: 'sources',
  labels: { singular: 'Источник', plural: 'Источники' },
  admin: {
    useAsTitle: 'name',
    defaultColumns: ['name', 'weight', 'active', 'feedUrl'],
    group: 'Конвейер',
    description: 'Мировые издания, из которых конвейер собирает новости (RSS/Atom).',
  },
  access: { read: isStaff, create: isEditor, update: isEditor, delete: isEditor },
  fields: [
    { name: 'name', label: 'Название', type: 'text', required: true },
    { name: 'siteUrl', label: 'Сайт', type: 'text' },
    { name: 'feedUrl', label: 'RSS/Atom-лента', type: 'text', required: true, unique: true },
    {
      name: 'weight',
      label: 'Авторитетность (1–10)',
      type: 'number',
      required: true,
      defaultValue: 6,
      min: 1,
      max: 10,
      admin: { description: 'Влияет на оценку важности сюжета' },
    },
    { name: 'active', label: 'Активен', type: 'checkbox', defaultValue: true },
    { name: 'notes', label: 'Заметки', type: 'textarea' },
  ],
}

export const Glossary: CollectionConfig = {
  slug: 'glossary',
  labels: { singular: 'Термин', plural: 'Глоссарий' },
  admin: {
    useAsTitle: 'term',
    defaultColumns: ['term', 'kk', 'doNotTranslate'],
    group: 'Конвейер',
    description: 'Как ИИ должен переводить IT-термины. Соблюдается при написании и проверке статей.',
  },
  access: { read: isStaff, create: isEditor, update: isEditor, delete: isEditor },
  fields: [
    { name: 'term', label: 'Термин (англ.)', type: 'text', required: true, unique: true },
    { name: 'kk', label: 'На казахском', type: 'text' },
    { name: 'doNotTranslate', label: 'Не переводить', type: 'checkbox', defaultValue: false },
    { name: 'note', label: 'Пояснение', type: 'text' },
  ],
}

export const Media: CollectionConfig = {
  slug: 'media',
  labels: { singular: 'Файл', plural: 'Медиа' },
  admin: { group: 'Контент' },
  access: { read: anyone, create: isStaff, update: isStaff, delete: isEditor },
  upload: {
    staticDir: 'media',
    mimeTypes: ['image/*'],
    imageSizes: [
      { name: 'card', width: 640, height: 360, position: 'centre' },
      { name: 'hero', width: 1280, height: 720, position: 'centre' },
      { name: 'og', width: 1200, height: 630, position: 'centre' },
    ],
    adminThumbnail: 'card',
  },
  fields: [
    { name: 'alt', label: 'Описание (alt)', type: 'text', required: true },
    { name: 'credit', label: 'Автор / лицензия', type: 'text', admin: { description: 'Обязательно для фото не нашей редакции' } },
  ],
}
