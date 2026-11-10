// Транслитерация казахской кириллицы для ЧПУ. Должна совпадать с pipeline/qtnews/slug.py
const MAP: Record<string, string> = {
  а: 'a', ә: 'a', б: 'b', в: 'v', г: 'g', ғ: 'g', д: 'd', е: 'e', ё: 'yo', ж: 'zh', з: 'z', и: 'i', й: 'i',
  к: 'k', қ: 'q', л: 'l', м: 'm', н: 'n', ң: 'ng', о: 'o', ө: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u',
  ұ: 'u', ү: 'u', ф: 'f', х: 'h', һ: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'shch', ъ: '', ы: 'y', і: 'i', ь: '',
  э: 'e', ю: 'yu', я: 'ya',
}

export function slugify(input: string, maxLen = 80): string {
  const latin = Array.from(input.toLowerCase())
    .map((ch) => MAP[ch] ?? ch.normalize('NFKD').replace(/[^\x00-\x7f]/g, ''))
    .join('')
  let slug = latin.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  if (slug.length > maxLen) slug = slug.slice(0, maxLen).replace(/-[^-]*$/, '')
  return slug || 'zhanalyq'
}
