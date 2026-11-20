import type { Access, GlobalConfig } from 'payload'
import { hasRole, hiddenUnless } from '../access'

/** Разработчик настраивает; бот конвейера читает токен, обновляет его и пишет статус отправки */
const devOrBot: Access = ({ req }) => hasRole(req.user as never, 'developer', 'bot')

export const TikTokSettings: GlobalConfig = {
  slug: 'tiktok-settings',
  label: 'TikTok',
  admin: {
    hidden: hiddenUnless('developer'),
    group: 'Конвейер',
    description: 'Новости сайта уходят в TikTok черновиками: во «Входящих» TikTok приходит уведомление, пост публикуется оттуда в пару нажатий.',
  },
  access: { read: devOrBot, update: devOrBot },
  fields: [
    { name: 'connect', type: 'ui', admin: { components: { Field: '/components/admin/TikTokConnect#TikTokConnect' } } },
    {
      type: 'row',
      fields: [
        { name: 'enabled', label: 'Отправлять черновики в TikTok', type: 'checkbox', defaultValue: false },
        {
          name: 'dailyLimit', label: 'Черновиков в сутки, не больше', type: 'number', defaultValue: 5, min: 1, max: 15,
          admin: { description: 'Конвейер отправляет не чаще одного черновика в 30 минут.' },
        },
        {
          name: 'lookbackHours', label: 'Брать статьи за последние, часов', type: 'number', defaultValue: 6, min: 1, max: 72,
        },
      ],
    },
    {
      name: 'hashtags', label: 'Постоянные хештеги', type: 'text', defaultValue: '#TechTalQ #технология #жаңалықтар',
    },
    // Служебное: заполняет подключение и конвейер
    { name: 'displayName', type: 'text', admin: { hidden: true } },
    { name: 'openId', type: 'text', admin: { hidden: true } },
    { name: 'accessToken', type: 'text', admin: { hidden: true } },
    { name: 'refreshToken', type: 'text', admin: { hidden: true } },
    { name: 'accessExpiresAt', type: 'date', admin: { hidden: true } },
    { name: 'refreshExpiresAt', type: 'date', admin: { hidden: true } },
    { name: 'lastPostAt', type: 'date', admin: { hidden: true } },
    { name: 'lastError', type: 'text', admin: { hidden: true } },
  ],
}
