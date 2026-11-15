import type { Access, FieldAccess } from 'payload'

/**
 * Роли:
 *  developer — разработчик: всё, включая технические разделы (источники, служебные поля, боты, роли);
 *  admin     — администратор издания: контент, настройки сайта и конвейера, пользователи (кроме разработчиков);
 *  editor    — редактор: статьи (включая публикацию и удаление), медиа, глоссарий;
 *  author    — автор: создаёт и правит статьи, загружает фото;
 *  bot       — конвейер, только API.
 */
export type Role = 'developer' | 'admin' | 'editor' | 'author' | 'bot'

type MaybeUser = { role?: Role | null } | null | undefined

export const hasRole = (user: MaybeUser, ...roles: Role[]): boolean =>
  Boolean(user?.role && roles.includes(user.role))

const STAFF: Role[] = ['developer', 'admin', 'editor', 'author', 'bot']

/** Любой сотрудник редакции, включая бота конвейера */
export const isStaff: Access = ({ req }) => hasRole(req.user as MaybeUser, ...STAFF)
/** Редактор и выше */
export const isEditor: Access = ({ req }) => hasRole(req.user as MaybeUser, 'developer', 'admin', 'editor')
/** Администратор и выше */
export const isAdmin: Access = ({ req }) => hasRole(req.user as MaybeUser, 'developer', 'admin')
export const isAdminField: FieldAccess = ({ req }) => hasRole(req.user as MaybeUser, 'developer', 'admin')
/** Только разработчик */
export const isDeveloper: Access = ({ req }) => hasRole(req.user as MaybeUser, 'developer')
export const anyone: Access = () => true

/** Для admin.hidden: раздел виден только перечисленным ролям */
export const hiddenUnless = (...roles: Role[]) =>
  ({ user }: { user: unknown }): boolean => !roles.includes(((user as { role?: string } | null)?.role || '') as Role)

/** Публика видит только опубликованное, редакция — всё */
export const publishedOrStaff: Access = ({ req }) => {
  if (hasRole(req.user as MaybeUser, ...STAFF)) return true
  return { status: { equals: 'published' } }
}
