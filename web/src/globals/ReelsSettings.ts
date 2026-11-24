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
        { name: 'showPresenter', label: 'Анимированный диктор во вступлении', type: 'checkbox', defaultValue: false },
        { name: 'perDay', label: 'Рилсов в сутки', type: 'number', defaultValue: 3, min: 1, max: 3 },
        { name: 'lookbackHours', label: 'Брать новости за последние, часов', type: 'number', defaultValue: 12, min: 2, max: 48 },
      ],
    },
    {
      type: 'row',
      fields: [
        {
          name: 'presenter', label: 'Голос диктора', type: 'select', defaultValue: 'm',
          options: [{ label: 'Мужской', value: 'm' }, { label: 'Женский', value: 'f' }],
          admin: { description: 'Диктор — картинка reels/assets/host.jpg; голос по умолчанию подбирается под него.' },
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
      type: 'row',
      fields: [
        {
          name: 'voiceStyle', label: 'Подача голоса', type: 'select', defaultValue: 'natural',
          options: [
            { label: 'Живая, эмоциональная', value: 'creative' },
            { label: 'Естественная', value: 'natural' },
            { label: 'Ровная, дикторская', value: 'robust' },
          ],
          admin: { description: 'Для модели eleven_v3: насколько свободно голос играет интонацией.' },
        },
        {
          name: 'audioTags', label: 'ИИ расставляет теги эмоций ([excited], [pause]…)', type: 'checkbox', defaultValue: false,
          admin: { description: 'Только для eleven_v3. На экране и в субтитрах теги не видны.' },
        },
      ],
    },
    {
      name: 'elevenlabsApiKey', label: 'API-ключ ElevenLabs', type: 'text',
      admin: { placeholder: 'sk_…', description: 'elevenlabs.io → Developers → API Keys. Никому не пересылайте.' },
    },
    {
      name: 'pixabayApiKey', label: 'API-ключ Pixabay (видео)', type: 'text',
      admin: { description: 'Бесплатно: pixabay.com/api/docs → после входа ключ показан в разделе «Parameters» (key).' },
    },
    {
      name: 'pexelsApiKey', label: 'API-ключ Pexels (видео-репортаж)', type: 'text',
      admin: {
        description: 'Бесплатно: pexels.com/api → «Your API Key». С ключом в середине новости идут тематические стоковые видео ' +
          'с подписью «Иллюстрациялық кадрлар». Пусто — только фото новости.',
      },
    },
    {
      type: 'row',
      fields: [
        { name: 'publishInstagram', label: 'Публиковать в Instagram Reels', type: 'checkbox', defaultValue: true },
        { name: 'publishTelegram', label: 'Публиковать в Telegram', type: 'checkbox', defaultValue: true },
        { name: 'publishTikTok', label: 'Черновиком в TikTok', type: 'checkbox', defaultValue: false },
      ],
    },
    {
      name: 'reviewChatId', label: 'Присылать готовые рилсы в Telegram-чат (ID)', type: 'text',
      admin: { description: 'Видео и готовый текст подписи для ручной публикации в Instagram. Бот — тот же, что в настройках Telegram.' },
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
