/**
 * Логотип TechTalQ по брендбуку: знак «Q» (кольцо + точка-сигнал + золотая диагональ) и словесная часть.
 * Кольцо красится в currentColor: Ink на светлом фоне, белый — на тёмном. Sky и Gold не меняются.
 */
export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg className="logo__mark" width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <circle cx="27" cy="27" r="20" stroke="currentColor" strokeWidth="9" />
      <circle cx="27" cy="27" r="4.2" fill="#00AFCA" />
      <path d="M39.5 39.5l15 15" stroke="#FFC72C" strokeWidth="8" strokeLinecap="round" />
    </svg>
  )
}

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <>
      <LogoMark size={size} />
      <span className="logo__text">TechTal<span className="logo__accent">Q</span></span>
    </>
  )
}
