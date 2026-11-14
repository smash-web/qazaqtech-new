const mark = { display: 'grid', placeItems: 'center', background: '#1463ff', color: '#fff', fontWeight: 800 } as const

export function Icon() {
  return <span style={{ ...mark, width: 26, height: 26, borderRadius: 7, fontSize: 16 }}>T</span>
}

export function Logo() {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, fontWeight: 800, fontSize: 30, letterSpacing: '-0.02em' }}>
      <span style={{ ...mark, width: 44, height: 44, borderRadius: 12, fontSize: 26 }}>T</span>
      <span>Tech<span style={{ color: '#1463ff' }}>Talq</span> <span style={{ fontWeight: 500, opacity: 0.6, fontSize: 18 }}>редакция</span></span>
    </span>
  )
}
