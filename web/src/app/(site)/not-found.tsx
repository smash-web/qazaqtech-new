import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="empty">
      <h1>Бет табылмады</h1>
      <p><Link href="/">Басты бетке оралу</Link></p>
    </div>
  )
}
