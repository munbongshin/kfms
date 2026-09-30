// Run: node --test src/utils/columnLabels.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { labelsFromSql, tablesReadBy } from './columnLabels.ts'

const schema = { appramt: '승인금액', cardno: '카드번호', merchname: '가맹점명' }
// What the server sends: the administrator's names for each function.
const terms = { sum: '합계', count: '건수', avg: '평균', max: '최대값', min: '최소값' }

test('an English alias on an aggregate gets the column name plus the aggregate', () => {
  // The bookmark saved before the Korean-alias rule: history #79.
  const sql = 'SELECT merchname, SUM(appramt) AS total_appr_amt FROM v_approval GROUP BY merchname ORDER BY total_appr_amt DESC LIMIT 5'
  assert.equal(labelsFromSql(sql, schema, terms).total_appr_amt, '승인금액 합계')
})

test('an unaliased aggregate is labelled under the name PostgreSQL gives it', () => {
  assert.equal(labelsFromSql('SELECT SUM(appramt) FROM v_approval', schema, terms).sum, '승인금액 합계')
})

test('count(*) is a plain count', () => {
  assert.equal(labelsFromSql('SELECT COUNT(*) AS cnt FROM v_approval', schema, terms).cnt, '건수')
})

test('count(distinct col) names what is counted', () => {
  const sql = 'SELECT COUNT(DISTINCT cardno) AS cards FROM v_approval'
  assert.equal(labelsFromSql(sql, schema, terms).cards, '카드번호 건수')
})

test('a qualified, quoted column still resolves', () => {
  const sql = 'SELECT AVG(a."appramt") AS avg_amt FROM v_approval a'
  assert.equal(labelsFromSql(sql, schema, terms).avg_amt, '승인금액 평균')
})

test('an unquoted alias is folded to lower case, as PostgreSQL returns it', () => {
  const sql = 'SELECT MAX(appramt) AS MaxAmt FROM v_approval'
  assert.equal(labelsFromSql(sql, schema, terms).maxamt, '승인금액 최대값')
})

test('a quoted English alias keeps its case', () => {
  const sql = 'SELECT MIN(appramt) AS "MinAmt" FROM v_approval'
  assert.equal(labelsFromSql(sql, schema, terms).MinAmt, '승인금액 최소값')
})

test('a Korean alias is left alone, it already reads correctly', () => {
  const sql = 'SELECT SUM(appramt) AS "총 매출액" FROM v_approval'
  assert.deepEqual(labelsFromSql(sql, schema, terms), {})
})

test('an uncommented column falls back to the aggregate name alone', () => {
  assert.equal(labelsFromSql('SELECT SUM(mystery) AS s FROM t', schema, terms).s, '합계')
})

test('the keyword after an unaliased aggregate is not taken for an alias', () => {
  const labels = labelsFromSql('SELECT SUM(appramt) FROM v_approval', schema, terms)
  assert.equal(labels.from, undefined)
})

test('an expression inside the aggregate is not guessed at', () => {
  const sql = 'SELECT SUM(price_per_unit * quantity) AS revenue FROM retail_sales'
  assert.equal(labelsFromSql(sql, schema, terms).revenue, undefined)
})

test('a renamed term is what the header says', () => {
  const custom = { ...terms, sum: '총액' }
  assert.equal(labelsFromSql('SELECT SUM(appramt) AS s FROM v_approval', schema, custom).s, '승인금액 총액')
})

test('a function the administrator has no term for is left unlabelled', () => {
  assert.deepEqual(labelsFromSql('SELECT SUM(appramt) AS s FROM v_approval', schema, {}), {})
})

test('tables the SQL reads are tried first, the rest keep their order', () => {
  const keys = ['card_data', 'v_approval', 'cats.bill']
  assert.deepEqual(tablesReadBy('SELECT * FROM v_approval', keys), ['v_approval', 'card_data', 'cats.bill'])
})

test('a schema-qualified table is found by its bare name', () => {
  assert.deepEqual(tablesReadBy('select * from cats.bill b', ['card_data', 'cats.bill']), ['cats.bill', 'card_data'])
})

test('a table name inside a longer word does not count as read', () => {
  assert.deepEqual(tablesReadBy('SELECT * FROM card_data_backup', ['card_data', 'other']), ['card_data', 'other'])
})

test('no SQL leaves the order alone', () => {
  assert.deepEqual(tablesReadBy('', ['b', 'a']), ['b', 'a'])
})
