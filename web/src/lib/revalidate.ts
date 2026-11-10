import { revalidateTag } from 'next/cache'

/** Сброс кэша сайта. Вне Next.js (seed, CLI) вызов безопасно игнорируется. */
export function revalidate(...tags: string[]) {
  for (const tag of tags) {
    try {
      revalidateTag(tag)
    } catch {
      /* нет контекста Next.js */
    }
  }
}
