/** A report's schedule as one line of Korean, e.g. 매주 월요일 08시. */
const DAYS = ['월', '화', '수', '목', '금', '토', '일']

export function describeSchedule(
  frequency: string,
  hour: number,
  weekday: number | null,
  day: number | null
): string {
  const at = `${String(hour).padStart(2, '0')}시`
  if (frequency === 'weekly') return `매주 ${DAYS[weekday ?? 0]}요일 ${at}`
  if (frequency === 'monthly') return `매월 ${day ?? 1}일 ${at}`
  return `매일 ${at}`
}
