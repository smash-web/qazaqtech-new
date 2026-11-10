import type { Access, FieldAccess } from 'payload'

export type Role = 'admin' | 'editor' | 'author' | 'bot'

type MaybeUser = { role?: Role | null } | null | undefined

export const hasRole = (user: MaybeUser, ...roles: Role[]): boolean =>
  Boolean(user?.role && roles.includes(user.role))

/** Любой сотрудник редакции, включая бота конвейера */
export const isStaff: Access = ({ req }) => hasRole(req.user as MaybeUser, 'admin', 'editor', 'author', 'bot')
/** Редактор или администратор */
export const isEditor: Access = ({ req }) => hasRole(req.user as MaybeUser, 'admin', 'editor')
export const isAdmin: Access = ({ req }) => hasRole(req.user as MaybeUser, 'admin')
export const isAdminField: FieldAccess = ({ req }) => hasRole(req.user as MaybeUser, 'admin')
export const anyone: Access = () => true

/** Публика видит только опубликованное, редакция — всё */
export const publishedOrStaff: Access = ({ req }) => {
  if (hasRole(req.user as MaybeUser, 'admin', 'editor', 'author', 'bot')) return true
  return { status: { equals: 'published' } }
}
