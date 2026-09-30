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
