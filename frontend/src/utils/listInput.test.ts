// Run: node --test src/utils/listInput.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mergeItems, parseItems, isIsoDate } from './listInput.ts'

test('one item per line, blanks and surrounding spaces dropped', () => {
  assert.deepEqual(parseItems('영화관\n  화   원 \n\n'), ['영화관', '화   원'])
})

test('commas, semicolons and tabs also separate items (pasted from a sheet or a sentence)', () => {
  assert.deepEqual(parseItems('영화관, 볼 링 장;화원\t주점'), ['영화관', '볼 링 장', '화원', '주점'])
})

test('windows line endings are handled', () => {
  assert.deepEqual(parseItems('a\r\nb\r\n'), ['a', 'b'])
})

test('spaces inside a name are kept (the data has names like 볼 링 장)', () => {
  assert.deepEqual(parseItems('볼 링 장'), ['볼 링 장'])
})

test('repeats within the pasted text count once', () => {
  assert.deepEqual(parseItems('a\nb\na'), ['a', 'b'])
})

test('merging adds only what is new and reports what was already there', () => {
  const out = mergeItems(['영화관'], ['영화관', '주점', '화원'])
  assert.deepEqual(out.list, ['영화관', '주점', '화원'])
  assert.deepEqual(out.added, ['주점', '화원'])
  assert.deepEqual(out.duplicates, ['영화관'])
})

test('merging into an empty list', () => {
  assert.deepEqual(mergeItems([], ['a']).list, ['a'])
})

test('the existing order is kept and the input list is not modified', () => {
  const existing = ['b', 'a']
  mergeItems(existing, ['c'])
  assert.deepEqual(existing, ['b', 'a'])
})

test('a real ISO date is recognised, an impossible one is not', () => {
  assert.equal(isIsoDate('2026-05-05'), true)
  assert.equal(isIsoDate('2026-02-30'), false)
  assert.equal(isIsoDate('2026-5-5'), false)
  assert.equal(isIsoDate('abc'), false)
})
