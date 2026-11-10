import { CopyLink } from './CopyLink'

/** Кнопки «Бөлісу»: обычные ссылки, без сторонних скриптов и трекеров */
export function Share({ url, title }: { url: string; title: string }) {
  const u = encodeURIComponent(url)
  const t = encodeURIComponent(title)
  const links = [
    { name: 'Telegram', href: `https://t.me/share/url?url=${u}&text=${t}` },
    { name: 'WhatsApp', href: `https://wa.me/?text=${t}%20${u}` },
    { name: 'Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${u}` },
    { name: 'X', href: `https://x.com/intent/post?url=${u}&text=${t}` },
  ]
  return (
    <div className="share" aria-label="Бөлісу">
      <span className="share__label">Бөлісу:</span>
      {links.map((l) => (
        <a key={l.name} href={l.href} target="_blank" rel="noopener nofollow" className="share__btn">{l.name}</a>
      ))}
      <CopyLink url={url} />
    </div>
  )
}
