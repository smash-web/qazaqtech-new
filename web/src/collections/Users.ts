import { APIError, type CollectionConfig, type Where } from 'payload'
import { hasRole, hiddenUnless, isAdmin, isAdminField, type Role } from '../access'

/** Учётные записи, которыми управляет только разработчик */
const PROTECTED: Role[] = ['developer', 'bot']

/** Разработчик видит всех; администратор — всех, кроме разработчиков и ботов (и себя); остальные — только себя */
const scope = (user: { id?: number | string; role?: Role | null } | null | undefined): boolean | Where => {
  if (hasRole(user, 'developer')) return true
  if (hasRole(user, 'admin')) return { or: [{ role: { not_in: PROTECTED } }, { id: { equals: user?.id } }] }
  return { id: { equals: user?.id } }
}

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
    hideAPIURL: true,
    hidden: hiddenUnless('developer', 'admin'),
  },
  access: {
    // Бот работает только через API и не входит в админку
    admin: ({ req }) => hasRole(req.user as never, 'developer', 'admin', 'editor', 'author'),
    read: ({ req }) => scope(req.user as never),
    create: isAdmin,
    update: ({ req }) => scope(req.user as never),
    delete: ({ req }) => {
      if (hasRole(req.user as never, 'developer')) return true
      if (hasRole(req.user as never, 'admin')) return { role: { not_in: PROTECTED } }
      return false
    },
  },
  hooks: {
    beforeChange: [
      async ({ data, operation, req, originalDoc }) => {
        // Первый зарегистрированный человек (не бот) становится разработчиком — владельцем системы
        if (operation === 'create' && data.role !== 'bot') {
          const { totalDocs } = await req.payload.count({
            collection: 'users', overrideAccess: true, where: { role: { not_equals: 'bot' } },
          })
          if (totalDocs === 0) data.role = 'developer'
        }
        // Назначать роли «разработчик» и «бот» может только разработчик (вызовы без пользователя — системные)
        const actor = req.user as { role?: Role } | null
        const changed = operation === 'create' || (data.role !== undefined && data.role !== originalDoc?.role)
        if (actor && !hasRole(actor, 'developer') && changed && PROTECTED.includes(data.role as Role)) {
          throw new APIError('Эту роль может назначить только разработчик.', 403)
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
      admin: {
        description: 'Автор пишет статьи. Редактор публикует и удаляет. Администратор управляет сайтом и людьми.',
      },
      // Администратор не видит в списке роли, которые не может назначить
      filterOptions: ({ options, req }) =>
        hasRole(req.user as never, 'developer')
          ? options
          : options.filter((o) => !PROTECTED.includes((typeof o === 'string' ? o : o.value) as Role)),
      options: [
        { label: 'Разработчик', value: 'developer' },
        { label: 'Администратор', value: 'admin' },
        { label: 'Редактор', value: 'editor' },
        { label: 'Автор', value: 'author' },
        { label: 'Бот конвейера (только API)', value: 'bot' },
      ],
    },
  ],
}
