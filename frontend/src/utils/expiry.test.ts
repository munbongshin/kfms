// Run: node --test src/utils/expiry.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeExpiry } from './expiry.ts'

const NOW = new Date('2026-09-30T00:00:00Z')
const inHours = (h: number) => new Date(NOW.getTime() + h * 3600_000).toISOString()

test('a fresh upload shows its hours', () => {
  assert.equal(describeExpiry(inHours(24), NOW), '24시간')
})

test('one hour left is singular', () => {
  assert.equal(describeExpiry(inHours(1), NOW), '1시간')
})

test('under an hour says so', () => {
  assert.equal(describeExpiry(inHours(0.2), NOW), '1시간 미만')
})

test('an expired upload warns that it will be deleted', () => {
  assert.match(describeExpiry(inHours(-5), NOW), /자동 삭제/)
})

test('extending by 24 hours adds a day to what is shown', () => {
  assert.equal(describeExpiry(inHours(3 + 24), NOW), '27시간')
})

test('a translator is used for every phrase', () => {
  const english = (key: string, params?: Record<string, string | number>) =>
    ({ '{n}시간': '{n} hours', '1시간': '1 hour', '1시간 미만': 'Less than 1 hour', '만료됨 — 곧 자동 삭제': 'Expired — deleted soon' }[key] || key)
      .replace('{n}', String(params?.n))
  assert.equal(describeExpiry(inHours(27), NOW, english), '27 hours')
  assert.equal(describeExpiry(inHours(1), NOW, english), '1 hour')
  assert.equal(describeExpiry(inHours(0.2), NOW, english), 'Less than 1 hour')
  assert.equal(describeExpiry(inHours(-5), NOW, english), 'Expired — deleted soon')
})
