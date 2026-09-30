/** Fills {name} placeholders; the default translator, which leaves the Korean text as it is. */
type Translate = (key: string, params?: Record<string, string | number>) => string

const asIs: Translate = (key, params) =>
  params ? key.replace(/\{(\w+)\}/g, (whole, name) => (name in params ? String(params[name]) : whole)) : key

/** How long an Excel upload has left, in words (Korean unless a translator is given). */
export function describeExpiry(expiresAt: string, now: Date = new Date(), tr: Translate = asIs): string {
  const diffHrs = Math.round((new Date(expiresAt).getTime() - now.getTime()) / (1000 * 60 * 60))

  // Past expiry the server keeps it for a grace period, then drops it.
  if (diffHrs < 0) return tr('만료됨 — 곧 자동 삭제')
  if (diffHrs < 1) return tr('1시간 미만')
  if (diffHrs === 1) return tr('1시간')
  return tr('{n}시간', { n: diffHrs })
}
