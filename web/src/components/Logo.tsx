/**
 * Логотип TechTalQ (файлы из брендбука в /public/brand).
 * theme="auto" — светлая версия на светлой теме и белая на тёмной (по системной теме, как и весь сайт);
 * theme="dark" — всегда белая версия (подвал на тёмном фоне).
 */
const W = 444
const H = 120

export function Logo({ height = 36, theme = 'auto' }: { height?: number; theme?: 'auto' | 'dark' }) {
  const width = Math.round((W / H) * height)
  if (theme === 'dark') {
    return <img className="logo__img" src="/brand/logo-dark.png" alt="TechTalQ" width={width} height={height} />
  }
  return (
    <picture>
      <source srcSet="/brand/logo-dark.png" media="(prefers-color-scheme: dark)" />
      <img className="logo__img" src="/brand/logo-light.png" alt="TechTalQ" width={width} height={height} />
    </picture>
  )
}
