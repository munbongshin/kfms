// Run: node --test src/utils/schedule.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeSchedule } from './schedule.ts'

test('daily names only the hour', () => {
  assert.equal(describeSchedule('daily', 9, null, null), '매일 09시')
})

test('weekly names the weekday, Monday first', () => {
  assert.equal(describeSchedule('weekly', 8, 0, null), '매주 월요일 08시')
  assert.equal(describeSchedule('weekly', 23, 6, null), '매주 일요일 23시')
})

test('monthly names the day of the month', () => {
  assert.equal(describeSchedule('monthly', 0, null, 15), '매월 15일 00시')
})

test('a missing weekday or day falls back rather than printing undefined', () => {
  assert.equal(describeSchedule('weekly', 9, null, null), '매주 월요일 09시')
  assert.equal(describeSchedule('monthly', 9, null, null), '매월 1일 09시')
})

test('an unknown frequency reads as daily', () => {
  assert.equal(describeSchedule('hourly', 9, null, null), '매일 09시')
})

test('a translator words the schedule in another language', () => {
  const table: Record<string, string> = {
    '{h}시': '{h}:00', '매주 {day} {at}': 'Every {day} at {at}', '월요일': 'Monday',
    '매월 {d}일 {at}': 'Monthly on day {d} at {at}', '매일 {at}': 'Daily at {at}',
  }
  const english = (key: string, params?: Record<string, string | number>) =>
    (table[key] ?? key).replace(/\{(\w+)\}/g, (whole, name) => String(params?.[name] ?? whole))
  assert.equal(describeSchedule('weekly', 8, 0, null, english), 'Every Monday at 08:00')
  assert.equal(describeSchedule('monthly', 0, null, 15, english), 'Monthly on day 15 at 00:00')
  assert.equal(describeSchedule('daily', 9, null, null, english), 'Daily at 09:00')
})
