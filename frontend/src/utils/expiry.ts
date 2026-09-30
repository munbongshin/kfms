/** How long an Excel upload has left, in words. */
export function describeExpiry(expiresAt: string, now: Date = new Date()): string {
  const diffHrs = Math.round((new Date(expiresAt).getTime() - now.getTime()) / (1000 * 60 * 60))

  // Past expiry the server keeps it for a grace period, then drops it.
  if (diffHrs < 0) return 'Expired — 곧 자동 삭제'
  if (diffHrs < 1) return 'Less than 1 hour'
  if (diffHrs === 1) return '1 hour'
  return `${diffHrs} hours`
}
