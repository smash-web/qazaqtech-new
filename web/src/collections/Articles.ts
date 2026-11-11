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
    defaultColumns: ['title', 'status', 'category', 'publishedAt', 'views'],
    listSearchableFields: ['title', 'excerpt'],
    group: 'Контент',
    description: 'Новости сайта. Статьи конвейера со статусом «На модерации» ждут вашей проверки.',
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
    // --- как пост: фото → заголовок → анонс → текст ------------------------------------
    { name: 'coverImage', label: 'Фото (обложка)', type: 'upload', relationTo: 'media', admin: { description: 'Нажмите, чтобы загрузить фото или выбрать из уже загруженных. Лучше горизонтальное.' } },
    { name: 'title', label: 'Заголовок', type: 'text', required: true, maxLength: 160 },
    { name: 'excerpt', label: 'Анонс', type: 'textarea', maxLength: 300, admin: { description: '1–2 предложения: показываются под заголовком и в карточке на главной.' } },
    { name: 'content', label: 'Текст статьи', type: 'richText', required: true },
    {
      type: 'collapsible',
      label: 'Источники и теги',
      admin: { initCollapsed: true },
      fields: [
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
          labels: { singular: 'Тег', plural: 'Теги' },
          fields: [{ name: 'tag', label: 'Тег', type: 'text', required: true }],
        },
      ],
    },
    {
      type: 'collapsible',
      label: 'SEO (необязательно)',
      admin: { initCollapsed: true },
      fields: [
        {
          type: 'group',
          name: 'meta',
          label: false,
          fields: [
            { name: 'title', label: 'SEO-заголовок', type: 'text', maxLength: 70 },
            { name: 'description', label: 'SEO-описание', type: 'textarea', maxLength: 170 },
          ],
        },
      ],
    },
    // --- боковая панель -------------------------------------------------------------
    {
      name: 'publishButton',
      type: 'ui',
      admin: { position: 'sidebar', components: { Field: '/components/admin/PublishButton#PublishButton' } },
    },
    { name: 'category', label: 'Рубрика', type: 'relationship', relationTo: 'categories', index: true, admin: { position: 'sidebar' } },
    {
      name: 'status',
      label: 'Статус',
      type: 'select',
      required: true,
      defaultValue: 'draft',
      index: true,
      admin: { position: 'sidebar', description: 'Меняется кнопкой «Опубликовать». Вручную — чтобы отклонить или вернуть в черновики.' },
      options: [
        { label: 'Черновик', value: 'draft' },
        { label: 'На модерации', value: 'review' },
        { label: 'Опубликовано', value: 'published' },
        { label: 'Отклонено', value: 'rejected' },
      ],
    },
    { name: 'publishedAt', label: 'Дата публикации', type: 'date', index: true, admin: { position: 'sidebar', description: 'Можно не трогать: поставится сама в момент публикации.', date: { pickerAppearance: 'dayAndTime' } } },
    { name: 'qaNotes', label: 'Замечания ИИ-проверки', type: 'textarea', admin: { position: 'sidebar', readOnly: true, condition: (data) => Boolean(data?.qaNotes) } },
    { name: 'views', label: 'Просмотры', type: 'number', defaultValue: 0, access: { update: () => false }, admin: { position: 'sidebar', readOnly: true } },
    {
      type: 'collapsible',
      label: 'Служебное',
      admin: { position: 'sidebar', initCollapsed: true },
      fields: [
        {
          name: 'slug',
          label: 'Адрес страницы (slug)',
          type: 'text',
          unique: true,
          index: true,
          admin: { description: 'Создаётся сам из заголовка. Менять не нужно.' },
          hooks: {
            beforeValidate: [({ value, data }) => (value ? slugify(String(value)) : slugify(String(data?.title || '')))],
          },
        },
        { name: 'needsTranslation', label: 'Нужен перевод', type: 'checkbox', defaultValue: false, index: true, admin: { description: 'Черновик конвейера без ИИ: текст источников на языке оригинала' } },
        { name: 'aiGenerated', label: 'Подготовлено ИИ', type: 'checkbox', defaultValue: false },
        { name: 'importanceScore', label: 'Оценка важности (0–10)', type: 'number', admin: { readOnly: true } },
        { name: 'pipelineStoryId', label: 'ID сюжета конвейера', type: 'number', unique: true, index: true, admin: { readOnly: true } },
      ],
    },
  ],
}
