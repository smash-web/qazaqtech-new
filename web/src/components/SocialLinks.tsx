import type { SiteSettingsDoc } from '@/lib/types'

const LABELS: Record<string, string> = {
  telegram: 'Telegram', instagram: 'Instagram', youtube: 'YouTube', facebook: 'Facebook', x: 'X', threads: 'Threads',
}

/** Ссылки на соцсети из «Настроек сайта»; пустые не выводятся */
export function SocialLinks({ social, className }: { social?: SiteSettingsDoc['social']; className?: string }) {
  const items = Object.entries(social || {}).filter(([k, v]) => LABELS[k] && typeof v === 'string' && v.startsWith('http'))
  if (!items.length) return null
  return (
    <nav className={className} aria-label="Әлеуметтік желілер">
      {items.map(([k, v]) => (
        <a key={k} href={v as string} target="_blank" rel="noopener">{LABELS[k]}</a>
      ))}
    </nav>
  )
}
