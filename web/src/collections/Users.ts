import type { CollectionConfig } from 'payload'
import { hasRole, isAdmin, isAdminField } from '../access'

export const Users: CollectionConfig = {
  slug: 'users',
  labels: { singular: 'Пользователь', plural: 'Пользователи' },
  auth: {
    useAPIKey: true, // ключ API для бота конвейера
    tokenExpiration: 60 * 60 * 12,
    maxLoginAttempts: 7,
    lockTime: 15 * 60 * 1000,
  },
  admin: {
    useAsTitle: 'email',
    defaultColumns: ['email', 'name', 'role'],
    group: 'Администрирование',
  },
  access: {
    // Бот работает только через API и не входит в админку
    admin: ({ req }) => hasRole(req.user as never, 'admin', 'editor', 'author'),
    read: ({ req }) => (hasRole(req.user as never, 'admin') ? true : { id: { equals: req.user?.id } }),
    create: isAdmin,
    update: ({ req }) => (hasRole(req.user as never, 'admin') ? true : { id: { equals: req.user?.id } }),
    delete: isAdmin,
  },
  hooks: {
    beforeChange: [
      // Первый зарегистрированный человек (не бот) становится администратором
      async ({ data, operation, req }) => {
        if (operation === 'create' && data.role !== 'bot') {
          const { totalDocs } = await req.payload.count({
            collection: 'users', overrideAccess: true, where: { role: { not_equals: 'bot' } },
          })
          if (totalDocs === 0) data.role = 'admin'
        }
        return data
      },
    ],
  },
  fields: [
    { name: 'name', label: 'Имя', type: 'text' },
    {
      name: 'role',
      label: 'Роль',
      type: 'select',
      required: true,
      defaultValue: 'author',
      saveToJWT: true,
      access: { update: isAdminField },
      options: [
        { label: 'Администратор', value: 'admin' },
        { label: 'Редактор', value: 'editor' },
        { label: 'Автор', value: 'author' },
        { label: 'Бот конвейера (только API)', value: 'bot' },
      ],
    },
  ],
}
