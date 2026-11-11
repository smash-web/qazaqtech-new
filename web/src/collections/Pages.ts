import type { CollectionConfig } from 'payload'
import { anyone, isEditor } from '../access'
import { revalidate } from '../lib/revalidate'
import { slugify } from '../lib/slugify'

/** Информационные страницы: «Біз туралы», «Редакциялық саясат», «Жарнама» и т. п. */
export const Pages: CollectionConfig = {
  slug: 'pages',
  labels: { singular: 'Страница', plural: 'Страницы' },
  admin: {
    useAsTitle: 'title',
    defaultColumns: ['title', 'slug', 'showInFooter', 'order'],
    group: 'Контент',
    hidden: ({ user }) => user?.role === 'author',
    description: 'Информационные страницы сайта. Адрес: /aqparat/<slug>',
    preview: (doc) => (doc?.slug ? `${process.env.NEXT_PUBLIC_SITE_URL || ''}/aqparat/${doc.slug}` : null),
  },
  defaultSort: 'order',
  access: { read: anyone, create: isEditor, update: isEditor, delete: isEditor },
  hooks: {
    afterChange: [({ doc }) => (revalidate('pages'), doc)],
    afterDelete: [({ doc }) => (revalidate('pages'), doc)],
  },
  fields: [
    { name: 'title', label: 'Заголовок', type: 'text', required: true },
    {
      name: 'slug',
      type: 'text',
      required: true,
      unique: true,
      index: true,
      admin: { position: 'sidebar' },
      hooks: { beforeValidate: [({ value, data }) => slugify(String(value || data?.title || ''))] },
    },
    { name: 'summary', label: 'Краткое описание (для SEO)', type: 'textarea', maxLength: 200 },
    { name: 'content', label: 'Текст', type: 'richText', required: true },
    { name: 'showInFooter', label: 'Показывать в меню и подвале', type: 'checkbox', defaultValue: true, admin: { position: 'sidebar' } },
    { name: 'order', label: 'Порядок', type: 'number', defaultValue: 100, admin: { position: 'sidebar' } },
  ],
}
