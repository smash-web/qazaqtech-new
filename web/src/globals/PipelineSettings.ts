import type { GlobalConfig } from 'payload'
import { isEditor, isStaff } from '../access'

export const DEFAULT_STYLE_GUIDE = `- Пишем для IT-специалистов, студентов и предпринимателей Казахстана.
- Тон нейтральный, информационный. Без кликбейта, восклицательных знаков и оценочных эпитетов.
- Заголовок: суть новости в одном предложении, глагол в прошедшем времени («таныстырды», «жариялады»).
- Первый абзац отвечает на вопросы: кто, что, когда.
- Суммы в долларах дублируем словами «млн/млрд доллар», даты — «10 қараша».
- Иностранные имена и бренды — в оригинальном написании латиницей.`

export const DEFAULT_GUIDANCE = `Приоритет: искусственный интеллект, крупные IT-компании, кибербезопасность, стартапы и инвестиции,
важные запуски продуктов, регулирование технологий, всё, что касается Казахстана и Центральной Азии.
Не берём: скидки и распродажи, слухи без подтверждения, рекламные материалы, обзоры нишевых гаджетов.`

export const PipelineSettings: GlobalConfig = {
  slug: 'pipeline-settings',
  label: 'Настройки конвейера',
  admin: { group: 'Конвейер' },
  access: { read: isStaff, update: isEditor },
  fields: [
    {
      type: 'row',
      fields: [
        { name: 'pipelineEnabled', label: 'Конвейер включён', type: 'checkbox', defaultValue: true },
        {
          name: 'autoPublish',
          label: 'Публиковать автоматически',
          type: 'checkbox',
          defaultValue: false,
          admin: {
            description:
              'Выкл. — статьи попадают на модерацию. Вкл. — публикуются сразу, если ИИ-проверка прошла без замечаний.',
          },
        },
      ],
    },
    {
      type: 'row',
      fields: [
        { name: 'dailyQuota', label: 'Статей в день', type: 'number', defaultValue: 18, min: 1, max: 200, required: true },
        { name: 'minScore', label: 'Мин. оценка важности (0–10)', type: 'number', defaultValue: 5.5, min: 0, max: 10, required: true },
        { name: 'publishFromHour', label: 'Публиковать с (час)', type: 'number', defaultValue: 7, min: 0, max: 23 },
        { name: 'publishToHour', label: 'Публиковать до (час)', type: 'number', defaultValue: 23, min: 1, max: 24 },
      ],
    },
    {
      name: 'selectionGuidance',
      label: 'Редакционная политика отбора',
      type: 'textarea',
      defaultValue: DEFAULT_GUIDANCE,
      admin: { description: 'Что считать важным. ИИ учитывает это при оценке сюжетов.' },
    },
    {
      name: 'styleGuide',
      label: 'Стилевой гайд',
      type: 'textarea',
      defaultValue: DEFAULT_STYLE_GUIDE,
      admin: { description: 'Правила написания текстов. ИИ следует им при подготовке статей.' },
    },
  ],
}
