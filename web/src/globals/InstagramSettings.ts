import type { Access, GlobalConfig } from 'payload'
import { hasRole, hiddenUnless } from '../access'

/** Разработчик настраивает; бот конвейера читает токен, обновляет его и пишет статус публикаций */
const devOrBot: Access = ({ req }) => hasRole(req.user as never, 'developer', 'bot')

export const InstagramSettings: GlobalConfig = {
  slug: 'instagram-settings',
  label: 'Instagram',
  admin: {
    hidden: hiddenUnless('developer'),
    group: 'Конвейер',
    description: 'Автоматическая публикация новостей сайта в Instagram. Пост — картинка 4:5 с заголовком и подпись с анонсом.',
  },
  access: { read: devOrBot, update: devOrBot },
  fields: [
    { name: 'connect', type: 'ui', admin: { components: { Field: '/components/admin/InstagramConnect#InstagramConnect' } } },
    {
      type: 'row',
      fields: [
        { name: 'enabled', label: 'Публиковать в Instagram', type: 'checkbox', defaultValue: false },
        {
          name: 'dailyLimit', label: 'Постов в сутки, не больше', type: 'number', defaultValue: 20, min: 1, max: 90,
          admin: { description: 'Instagram разрешает до 100 постов через API в сутки. Конвейер выкладывает не чаще одного поста в 30 минут.' },
        },
        {
          name: 'lookbackHours', label: 'Брать статьи за последние, часов', type: 'number', defaultValue: 6, min: 1, max: 72,
          admin: { description: 'Более старые статьи в Instagram не уходят — чтобы после включения не выложить весь архив.' },
        },
      ],
    },
    {
      name: 'hashtags', label: 'Постоянные хештеги', type: 'text', defaultValue: '#TechTalQ #технология #жаңалықтар',
      admin: { description: 'Добавляются к каждому посту вместе с хештегом рубрики.' },
    },
    // Служебное: заполняет подключение и конвейер
    { name: 'username', type: 'text', admin: { hidden: true } },
    { name: 'igUserId', type: 'text', admin: { hidden: true } },
    { name: 'accessToken', type: 'text', admin: { hidden: true } },
    { name: 'tokenUpdatedAt', type: 'date', admin: { hidden: true } },
    { name: 'tokenExpiresAt', type: 'date', admin: { hidden: true } },
    { name: 'lastPostAt', type: 'date', admin: { hidden: true } },
    { name: 'lastError', type: 'text', admin: { hidden: true } },
  ],
}
