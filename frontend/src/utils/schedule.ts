type Translate = (key: string, params?: Record<string, string | number>) => string

const asIs: Translate = (key, params) =>
  params ? key.replace(/\{(\w+)\}/g, (whole, name) => (name in params ? String(params[name]) : whole)) : key

/** Monday first, as the server numbers them. */
const WEEKDAYS = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']

/** A report's schedule as one line, e.g. 매주 월요일 08시 (Korean unless a translator is given). */
export function describeSchedule(
  frequency: string,
  hour: number,
  weekday: number | null,
  day: number | null,
  tr: Translate = asIs
): string {
  const at = tr('{h}시', { h: String(hour).padStart(2, '0') })
  if (frequency === 'weekly') return tr('매주 {day} {at}', { day: tr(WEEKDAYS[weekday ?? 0]), at })
  if (frequency === 'monthly') return tr('매월 {d}일 {at}', { d: day ?? 1, at })
  return tr('매일 {at}', { at })
}
