import type { CollectionAfterChangeHook, CollectionAfterDeleteHook, CollectionConfig } from 'payload'
import { isEditor, isStaff, publishedOrStaff } from '../access'
import { revalidate } from '../lib/revalidate'
import { slugify } from '../lib/slugify'

const revalidateSite = () => revalidate('articles')

const afterChange: CollectionAfterChangeHook = ({ doc, previousDoc }) => {
  if (doc.status === 'published' || previousDoc?.status === 'published') revalidateSite()
  return doc
}
const afterDelete: CollectionAfterDeleteHook = ({ doc }) => {
  if (doc.status === 'published') revalidateSite()
  return doc
}

export const Articles: CollectionConfig = {
  slug: 'articles',
  labels: { singular: 'Статья', plural: 'Статьи' },
  admin: {
    useAsTitle: 'title',
    defaultColumns: ['title', 'status', 'category', 'importanceScore', 'needsTranslation', 'publishedAt'],
    listSearchableFields: ['title', 'excerpt'],
    group: 'Контент',
    description: 'Очередь модерации: отфильтруйте по статусу «На модерации».',
    preview: (doc) =>
      doc?.slug ? `${process.env.NEXT_PUBLIC_SITE_URL || ''}/zhanalyq/${doc.slug}` : null,
  },
  defaultSort: '-createdAt',
  access: {
    read: publishedOrStaff,
    create: isStaff,
    update: isStaff,
    delete: isEditor,
  },
  hooks: {
    beforeChange: [
      ({ data, originalDoc }) => {
        if (data.status === 'published' && !data.publishedAt && !originalDoc?.publishedAt) {
          data.publishedAt = new Date().toISOString()
        }
        return data
      },
    ],
    afterChange: [afterChange],
    afterDelete: [afterDelete],
  },
  fields: [
    { name: 'title', label: 'Заголовок', type: 'text', required: true, maxLength: 160 },
    {
      name: 'slug',
      label: 'URL (slug)',
      type: 'text',
      required: true,
      unique: true,
      index: true,
      admin: { position: 'sidebar', description: 'Заполняется автоматически из заголовка' },
      hooks: {
        beforeValidate: [({ value, data }) => (value ? slugify(String(value)) : slugify(String(data?.title || '')))],
      },
    },
    { name: 'excerpt', label: 'Лид / анонс', type: 'textarea', maxLength: 300 },
    { name: 'coverImage', label: 'Обложка', type: 'upload', relationTo: 'media' },
    { name: 'content', label: 'Текст', type: 'richText', required: true },
    {
      name: 'sources',
      label: 'Первоисточники',
      type: 'array',
      labels: { singular: 'Источник', plural: 'Источники' },
      fields: [
        { name: 'name', label: 'Издание', type: 'text', required: true },
        { name: 'url', label: 'Ссылка', type: 'text', required: true },
      ],
    },
    {
      name: 'tags',
      label: 'Теги',
      type: 'array',
      fields: [{ name: 'tag', label: 'Тег', type: 'text', required: true }],
    },
    {
      type: 'group',
      name: 'meta',
      label: 'SEO',
      fields: [
        { name: 'title', label: 'SEO-заголовок', type: 'text', maxLength: 70 },
        { name: 'description', label: 'SEO-описание', type: 'textarea', maxLength: 170 },
      ],
    },
    // --- боковая панель -------------------------------------------------------------
    {
      name: 'status',
      label: 'Статус',
      type: 'select',
      required: true,
      defaultValue: 'draft',
      index: true,
      admin: { position: 'sidebar' },
      options: [
        { label: 'Черновик', value: 'draft' },
        { label: 'На модерации', value: 'review' },
        { label: 'Опубликовано', value: 'published' },
        { label: 'Отклонено', value: 'rejected' },
      ],
    },
    { name: 'publishedAt', label: 'Дата публикации', type: 'date', index: true, admin: { position: 'sidebar', date: { pickerAppearance: 'dayAndTime' } } },
    { name: 'category', label: 'Рубрика', type: 'relationship', relationTo: 'categories', index: true, admin: { position: 'sidebar' } },
    { name: 'needsTranslation', label: 'Нужен перевод', type: 'checkbox', defaultValue: false, index: true, admin: { position: 'sidebar', description: 'Черновик конвейера без ИИ: текст источников на языке оригинала' } },
    { name: 'aiGenerated', label: 'Подготовлено ИИ', type: 'checkbox', defaultValue: false, admin: { position: 'sidebar' } },
    { name: 'importanceScore', label: 'Оценка важности (0–10)', type: 'number', admin: { position: 'sidebar', readOnly: true } },
    { name: 'qaNotes', label: 'Замечания ИИ-проверки', type: 'textarea', admin: { position: 'sidebar', readOnly: true } },
    { name: 'pipelineStoryId', label: 'ID сюжета конвейера', type: 'number', unique: true, index: true, admin: { position: 'sidebar', readOnly: true } },
  ],
}
