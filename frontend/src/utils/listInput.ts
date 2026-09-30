/**
 * Adding items to a list one at a time or many at once (pasted lines, a column
 * copied from a sheet, a comma-separated sentence).
 */

/** Items in `text`, separated by new lines, tabs, commas or semicolons; trimmed, no blanks, no repeats. */
export function parseItems(text: string): string[] {
  const seen = new Set<string>()
  const items: string[] = []
  for (const part of text.split(/[\r\n\t,;]+/)) {
    const item = part.trim()
    if (item && !seen.has(item)) {
      seen.add(item)
      items.push(item)
    }
  }
  return items
}

/** `existing` plus whatever in `incoming` is new, with what was new and what was already there. */
export function mergeItems(existing: string[], incoming: string[]) {
  const have = new Set(existing)
  const added: string[] = []
  const duplicates: string[] = []
  for (const item of incoming) {
    if (have.has(item)) duplicates.push(item)
    else {
      have.add(item)
      added.push(item)
    }
  }
  return { list: [...existing, ...added], added, duplicates }
}

/** YYYY-MM-DD that is a real calendar day. */
export function isIsoDate(text: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return false
  const d = new Date(`${text}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === text
}
