'use client'

import { useState } from 'react'

export function CopyLink({ url }: { url: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      className="share__btn"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(url)
          setDone(true)
          setTimeout(() => setDone(false), 2000)
        } catch {
          window.prompt('Сілтемені көшіріңіз:', url)
        }
      }}
    >
      {done ? 'Көшірілді ✓' : 'Сілтемені көшіру'}
    </button>
  )
}
