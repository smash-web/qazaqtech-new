import type { Access, GlobalConfig } from 'payload'
import { hasRole, hiddenUnless } from '../access'

/** Разработчик настраивает; бот конвейера читает настройки и пишет статус публикации */
const devOrBot: Access = ({ req }) => hasRole(req.user as never, 'developer', 'bot')

export const TelegramSettings: GlobalConfig = {
  slug: 'telegram-settings',
  label: 'Telegram',
  admin: {
    hidden: hiddenUnless('developer'),
    group: 'Конвейер',
    description:
      'Новости сайта публикуются в Telegram-канал: картинка, заголовок, анонс и кнопка «Толық оқу». ' +
      'Бот (создаётся в @BotFather) должен быть администратором канала с правом публиковать сообщения.',
  },
  access: { read: devOrBot, update: devOrBot },
  hooks: {
    // Сменили канал или бота — при следующем запуске конвейер заново проверит подключение
    beforeChange: [
      ({ data, originalDoc }) => {
        if (originalDoc && (data.channel !== originalDoc.channel || data.botToken !== originalDoc.botToken)) {
          data.channelTitle = ''
        }
        return data
      },
    ],
  },
  fields: [
    {
      type: 'row',
      fields: [
        { name: 'enabled', label: 'Публиковать новости в Telegram', type: 'checkbox', defaultValue: false },
        {
          name: 'dailyLimit', label: 'Постов в сутки, не больше', type: 'number', defaultValue: 40, min: 1, max: 100,
          admin: { description: 'Конвейер запускается каждые 30 минут и выкладывает до 3 новостей за раз.' },
        },
        { name: 'lookbackHours', label: 'Брать статьи за последние, часов', type: 'number', defaultValue: 6, min: 1, max: 72 },
      ],
    },
    {
      name: 'channel', label: 'Канал', type: 'text',
      admin: { placeholder: '@techtalq', description: 'Публичный: @имя или ссылка t.me/имя. Закрытый: числовой id вида -100…' },
    },
    {
      name: 'botToken', label: 'Токен бота', type: 'text',
      admin: { placeholder: '123456789:AA…', description: 'Выдаёт @BotFather после команды /newbot. Никому не пересылайте.' },
    },
    // Статус — заполняет конвейер
    {
      type: 'row',
      fields: [
        { name: 'channelTitle', label: 'Подключённый канал', type: 'text', admin: { readOnly: true } },
        { name: 'lastPostAt', label: 'Последний пост', type: 'date', admin: { readOnly: true, date: { pickerAppearance: 'dayAndTime' } } },
      ],
    },
    { name: 'lastError', label: 'Последняя ошибка', type: 'text', admin: { readOnly: true } },
  ],
}
