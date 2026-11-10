import type { GlobalConfig } from 'payload'
import { anyone, isEditor } from '../access'
import { revalidate } from '../lib/revalidate'

/** Настройки сайта: описание, контакты, соцсети. Пустые поля на сайте не показываются. */
export const SiteSettings: GlobalConfig = {
  slug: 'site-settings',
  label: 'Настройки сайта',
  admin: { group: 'Администрирование' },
  access: { read: anyone, update: isEditor },
  hooks: { afterChange: [({ doc }) => (revalidate('settings'), doc)] },
  fields: [
    {
      name: 'about',
      label: 'Коротко о портале (подвал)',
      type: 'textarea',
      defaultValue:
        'Әлемдік технология жаңалықтары қазақ тілінде: жасанды интеллект, IT-компаниялар, стартаптар, киберқауіпсіздік және гаджеттер.',
    },
    {
      type: 'row',
      fields: [
        { name: 'email', label: 'E-mail редакции', type: 'email' },
        { name: 'adsEmail', label: 'E-mail по рекламе', type: 'email' },
      ],
    },
    {
      name: 'social',
      label: 'Соцсети',
      type: 'group',
      fields: [
        {
          type: 'row',
          fields: [
            { name: 'telegram', label: 'Telegram', type: 'text', admin: { placeholder: 'https://t.me/...' } },
            { name: 'instagram', label: 'Instagram', type: 'text' },
            { name: 'youtube', label: 'YouTube', type: 'text' },
          ],
        },
        {
          type: 'row',
          fields: [
            { name: 'facebook', label: 'Facebook', type: 'text' },
            { name: 'x', label: 'X (Twitter)', type: 'text' },
            { name: 'threads', label: 'Threads', type: 'text' },
          ],
        },
      ],
    },
  ],
}
