import type { Access, GlobalConfig } from 'payload'
import { hasRole, hiddenUnless } from '../access'

/** Разработчик настраивает; бот конвейера читает настройки и пишет статус */
const devOrBot: Access = ({ req }) => hasRole(req.user as never, 'developer', 'bot')

export const ReelsSettings: GlobalConfig = {
  slug: 'reels-settings',
  label: 'Рилсы',
  admin: {
    hidden: hiddenUnless('developer'),
    group: 'Конвейер',
    description:
      'Рилсы с анимированным диктором: ИИ пишет текст, ElevenLabs озвучивает, GitHub Actions собирает видео ' +
      '(студия → новость на фоне → концовка) и публикует его. Запуски: 10:30, 15:30 и 20:30 по Алматы.',
  },
  access: { read: devOrBot, update: devOrBot },
  fields: [
    {
      type: 'row',
      fields: [
        { name: 'enabled', label: 'Делать рилсы', type: 'checkbox', defaultValue: false },
        { name: 'perDay', label: 'Рилсов в сутки', type: 'number', defaultValue: 3, min: 1, max: 3 },
        { name: 'lookbackHours', label: 'Брать новости за последние, часов', type: 'number', defaultValue: 12, min: 2, max: 48 },
      ],
    },
    {
      type: 'row',
      fields: [
        {
          name: 'presenter', label: 'Диктор', type: 'select', defaultValue: 'f',
          options: [{ label: 'Ведущая', value: 'f' }, { label: 'Ведущий', value: 'm' }],
        },
        {
          name: 'voiceId', label: 'ID голоса ElevenLabs', type: 'text',
          admin: { description: 'Voices → голос → «⋯» → Copy voice ID. Пусто — стандартный голос под выбранного диктора.' },
        },
        {
          name: 'model', label: 'Модель озвучки', type: 'text', defaultValue: 'eleven_v3',
          admin: { description: 'Казахский поддерживают модели v3 и новее.' },
        },
      ],
    },
    {
      name: 'elevenlabsApiKey', label: 'API-ключ ElevenLabs', type: 'text',
      admin: { placeholder: 'sk_…', description: 'elevenlabs.io → Developers → API Keys. Никому не пересылайте.' },
    },
    {
      type: 'row',
      fields: [
        { name: 'publishInstagram', label: 'Публиковать в Instagram Reels', type: 'checkbox', defaultValue: true },
        { name: 'publishTelegram', label: 'Публиковать в Telegram', type: 'checkbox', defaultValue: true },
        { name: 'publishTikTok', label: 'Черновиком в TikTok', type: 'checkbox', defaultValue: false },
      ],
    },
    // Статус — заполняет конвейер
    {
      type: 'row',
      fields: [
        { name: 'lastReelAt', label: 'Последний рилс', type: 'date', admin: { readOnly: true, date: { pickerAppearance: 'dayAndTime' } } },
        { name: 'lastVideoUrl', label: 'Видео последнего рилса', type: 'text', admin: { readOnly: true } },
      ],
    },
    { name: 'lastError', label: 'Последняя ошибка', type: 'text', admin: { readOnly: true } },
  ],
}
