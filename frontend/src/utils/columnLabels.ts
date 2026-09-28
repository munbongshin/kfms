/**
 * Korean headers for computed result columns, read off the SQL that made them.
 *
 * New SQL is asked to alias computed columns in Korean, but SQL saved earlier
 * (bookmarks, history) still returns names like `total_appr_amt` or `sum`.
 * `SUM(appramt) AS total_appr_amt` says exactly what the column is, so its
 * header can be built from the column's business name: 승인금액 합계.
 */

const AGGREGATE_LABELS: Record<string, string> = {
  sum: '합계',
  count: '건수',
  avg: '평균',
  max: '최대값',
  min: '최소값',
}

// FN( [DISTINCT] [qualifier.]column | * ) [AS alias]
// Only a bare column or * inside: an expression such as price * quantity has
// no single business name, so it is not guessed at.
const AGGREGATE = new RegExp(
  String.raw`\b(sum|count|avg|max|min)\s*\(\s*(?:distinct\s+)?` +
    String.raw`((?:"?\w+"?\.)?"?\w+"?|\*)\s*\)` +
    String.raw`(?:\s+as\s+("[^"]+"|\w+))?`,
  'gi'
)

const ASCII_NAME = /^[\x20-\x7e]+$/

function bare(identifier: string): string {
  const last = identifier.split('.').pop() || identifier
  return last.startsWith('"') ? last.slice(1, -1) : last.toLowerCase()
}

/** Result column name -> Korean label, for the computed columns in `sql`. */
export function labelsFromSql(
  sql: string,
  columnLabels: Record<string, string>
): Record<string, string> {
  const labels: Record<string, string> = {}

  for (const match of sql.matchAll(AGGREGATE)) {
    const [, fn, arg, alias] = match
    const aggregate = AGGREGATE_LABELS[fn.toLowerCase()]

    // Without AS, PostgreSQL names the column after the function.
    const name = alias
      ? alias.startsWith('"') ? alias.slice(1, -1) : alias.toLowerCase()
      : fn.toLowerCase()

    // A Korean alias already reads correctly.
    if (!ASCII_NAME.test(name)) continue

    const subject = arg === '*' ? undefined : columnLabels[bare(arg)]
    labels[name] = subject ? `${subject} ${aggregate}` : aggregate
  }

  return labels
}

/** The names PostgreSQL gives unaliased expressions, for SQL too complex to read. */
export const DEFAULT_EXPRESSION_LABELS: Record<string, string> = {
  ...AGGREGATE_LABELS,
  '?column?': '계산값',
}
