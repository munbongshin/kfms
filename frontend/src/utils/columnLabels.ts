/**
 * Korean headers for computed result columns, read off the SQL that made them.
 *
 * New SQL is asked to alias computed columns in Korean, but SQL saved earlier
 * (bookmarks, history) still returns names like `total_appr_amt` or `sum`.
 * `SUM(appramt) AS total_appr_amt` says exactly what the column is, so its
 * header can be built from the column's business name: 승인금액 합계.
 *
 * What SUM, COUNT ... are called (합계, 건수 ...) is not decided here: the server
 * sends the administrator's terms, keyed by function name.
 */

/**
 * Table keys reordered so the ones `sql` reads come first, otherwise unchanged.
 * A column name can carry a different label in different tables; a result only
 * has the bare name, so the tables the SQL mentions get to name it first.
 */
export function tablesReadBy(sql: string, tableKeys: string[]): string[] {
  const words = new Set(sql.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [])
  const bareName = (key: string) => (key.split('.').pop() || key).toLowerCase()
  const read = tableKeys.filter((key) => words.has(bareName(key)))
  return [...read, ...tableKeys.filter((key) => !read.includes(key))]
}

/** Function name (sum, count ...) -> what a column computed with it is called. */
export type ExpressionTerms = Record<string, string>

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
  columnLabels: Record<string, string>,
  terms: ExpressionTerms
): Record<string, string> {
  const labels: Record<string, string> = {}

  for (const match of sql.matchAll(AGGREGATE)) {
    const [, fn, arg, alias] = match
    const aggregate = terms[fn.toLowerCase()]
    if (!aggregate) continue

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
