// Run: node --test src/utils/access.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { canSee } from './access.ts'

test('no restriction means everyone, even before the role is known', () => {
  assert.equal(canSee(undefined, 'viewer'), true)
  assert.equal(canSee(undefined, null), true)
})

test('a listed role may see it', () => {
  assert.equal(canSee(['admin', 'auditor'], 'auditor'), true)
})

test('an unlisted role may not', () => {
  assert.equal(canSee(['admin', 'auditor'], 'viewer'), false)
  assert.equal(canSee(['admin'], 'auditor'), false)
})

test('a restricted item is hidden until the role is known', () => {
  assert.equal(canSee(['admin'], null), false)
})
