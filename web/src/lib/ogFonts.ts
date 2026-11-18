import 'server-only'

const fontCache = new Map<string, Promise<ArrayBuffer | null>>()

/** Шрифт из Google Fonts только с нужными глифами (параметр text): Inter — с казахскими буквами, Space Grotesk — логотип */
export function loadFont(family: string, weight: number, text: string): Promise<ArrayBuffer | null> {
  const key = `${family}:${weight}:${text}`
  if (!fontCache.has(key)) {
    fontCache.set(key, (async () => {
      try {
        const url = `https://fonts.googleapis.com/css2?family=${family.replace(/ /g, '+')}:wght@${weight}&text=${encodeURIComponent(text)}`
        const css = await (await fetch(url)).text()
        const src = css.match(/src: url\((.+?)\) format\('(opentype|truetype)'\)/)
        if (!src) return null
        const res = await fetch(src[1])
        return res.ok ? await res.arrayBuffer() : null
      } catch {
        return null
      }
    })())
    if (fontCache.size > 200) fontCache.delete(fontCache.keys().next().value as string)
  }
  return fontCache.get(key)!
}
