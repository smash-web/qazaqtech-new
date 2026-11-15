/** Логотип TechTalQ в админке (брендбук): кольцо — цвет текста темы, точка Sky, диагональ Gold. */
function Mark({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <circle cx="27" cy="27" r="20" stroke="currentColor" strokeWidth="9" />
      <circle cx="27" cy="27" r="4.2" fill="#00AFCA" />
      <path d="M39.5 39.5l15 15" stroke="#FFC72C" strokeWidth="8" strokeLinecap="round" />
    </svg>
  )
}

export function Icon() {
  return <Mark size={26} />
}

export function Logo() {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, fontWeight: 700, fontSize: 32, letterSpacing: '-0.02em',
      fontFamily: "'Space Grotesk', 'Inter', system-ui, sans-serif" }}>
      <Mark size={46} />
      <span>TechTal<span style={{ color: '#00AFCA' }}>Q</span> <span style={{ fontWeight: 500, opacity: 0.6, fontSize: 18 }}>редакция</span></span>
    </span>
  )
}
