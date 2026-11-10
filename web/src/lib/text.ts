/** Плоский текст из Lexical JSON (для времени чтения и описаний) */
export function lexicalText(node: unknown): string {
  if (!node || typeof node !== 'object') return ''
  const n = node as { text?: string; children?: unknown[]; root?: unknown }
  if (n.root) return lexicalText(n.root)
  if (typeof n.text === 'string') return n.text
  return (n.children || []).map(lexicalText).join(' ')
}

/** Минуты чтения (≈180 слов/мин для казахского текста), минимум 1 */
export function readingMinutes(content: unknown): number {
  const words = lexicalText(content).split(/\s+/).filter(Boolean).length
  return Math.max(1, Math.round(words / 180))
}
