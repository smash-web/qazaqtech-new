/**
 * Логотип TechTalQ (файлы из брендбука в /public/brand).
 * theme="auto" — светлая версия на светлой теме и белая на тёмной (тема — переключатель на сайте или система);
 * theme="dark" — всегда белая версия (подвал на тёмном фоне).
 */
const W = 444
const H = 120

export function Logo({ height = 36, theme = 'auto' }: { height?: number; theme?: 'auto' | 'dark' }) {
  const width = Math.round((W / H) * height)
  if (theme === 'dark') {
    return <img className="logo__img" src="/brand/logo-dark.png" alt="TechTalQ" width={width} height={height} />
  }
  // обе версии в разметке, нужную показывает CSS по теме (выбранной на сайте или системной)
  return (
    <>
      <img className="logo__img logo__img--light" src="/brand/logo-light.png" alt="TechTalQ" width={width} height={height} />
      <img className="logo__img logo__img--dark" src="/brand/logo-dark.png" alt="" aria-hidden="true" width={width} height={height} />
    </>
  )
}
