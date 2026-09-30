// Run: node --test src/i18n/i18n.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { escapeHtml, fill, parseLocale, translate, translateHtml } from './core.ts'
import { en } from './en.ts'

const catalog = { '질문하기': 'Ask', '{n}건을 삭제했습니다': 'Deleted {n} items' }

test('Korean returns the key itself', () => {
  assert.equal(translate('ko', catalog, '질문하기'), '질문하기')
})

test('English looks the key up', () => {
  assert.equal(translate('en', catalog, '질문하기'), 'Ask')
})

test('a missing English entry falls back to the Korean text', () => {
  assert.equal(translate('en', catalog, '없는 문구'), '없는 문구')
})

test('values fill their placeholders in both languages', () => {
  assert.equal(translate('ko', catalog, '{n}건을 삭제했습니다', { n: 3 }), '3건을 삭제했습니다')
  assert.equal(translate('en', catalog, '{n}건을 삭제했습니다', { n: 3 }), 'Deleted 3 items')
})

test('a placeholder without a value is left as written', () => {
  assert.equal(fill('{a} and {b}', { a: 1 }), '1 and {b}')
})

test('the stored language is read strictly', () => {
  assert.equal(parseLocale('en'), 'en')
  for (const v of ['ko', 'fr', '', null, undefined, 3]) assert.equal(parseLocale(v), 'ko')
})

test('html text keeps its own markup but escapes the values put into it', () => {
  const c = { '<b>{name}</b>를 삭제했습니다': 'Deleted <b>{name}</b>' }
  assert.equal(
    translateHtml('ko', c, '<b>{name}</b>를 삭제했습니다', { name: '<img src=x onerror=1>' }),
    '<b>&lt;img src=x onerror=1&gt;</b>를 삭제했습니다'
  )
  assert.equal(translateHtml('en', c, '<b>{name}</b>를 삭제했습니다', { name: 'a&b' }), 'Deleted <b>a&amp;b</b>')
})

test('escaping covers the characters that matter in markup', () => {
  assert.equal(escapeHtml('<a href="x">&</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;')
})

// --- the catalog covers the source -------------------------------------------------------------------

const SRC = fileURLToPath(new URL('..', import.meta.url))

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === 'i18n' ? [] : sources(path)
    // The help page stays in Korean; tests are not screens.
    return /\.(vue|ts)$/.test(name) && !name.endsWith('.test.ts') && name !== 'HelpView.vue' ? [path] : []
  })
}

function withoutComments(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

const unescape = (s: string) => s.replace(/\\(['"`\\])/g, '$1').replace(/\\n/g, '\n')

/** Literal keys passed to t(...), $t(...) or $th(...). */
function usedKeys(text: string): string[] {
  const call = /(?:\$th?|\bth?|\btr)\(\s*(['"`])((?:\\.|(?!\1)[^\\])*)\1/g
  return [...withoutComments(text).matchAll(call)].map((m) => unescape(m[2]))
}

/** Every quoted string that holds Hangul: a constant such as a label list is translated where it is shown. */
function koreanLiterals(text: string): string[] {
  const literal = /(['"])((?:\\.|(?!\1)[^\\\n])*)\1/g
  return [...withoutComments(text).matchAll(literal)].map((m) => unescape(m[2])).filter((k) => /[가-힣]/.test(k))
}

// The names of the languages themselves are shown as written, whatever the language is.
const SHOWN_AS_WRITTEN = new Set(['한글'])

test('every literal key used in the source has an English entry', () => {
  const missing = new Set<string>()
  for (const file of sources(SRC)) {
    for (const key of usedKeys(readFileSync(file, 'utf-8'))) {
      if (/[가-힣]/.test(key) && !(key in en)) missing.add(key)
    }
  }
  assert.deepEqual([...missing], [])
})

test('every Korean string in the screens has an English entry (constants included)', () => {
  const missing = new Set<string>()
  for (const file of sources(SRC)) {
    for (const key of koreanLiterals(readFileSync(file, 'utf-8'))) {
      // Skip a t(...) call written inside a template attribute: its outer quotes look like a string.
      if (/\$th?\(|\bt\(/.test(key)) continue
      if (!(key in en) && !SHOWN_AS_WRITTEN.has(key)) missing.add(key)
    }
  }
  assert.deepEqual([...missing], [])
})

test('no English entry is empty', () => {
  for (const [key, value] of Object.entries(en)) assert.ok(value.trim(), key)
})

test('an English entry keeps the same placeholders as its Korean key', () => {
  const names = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',')
  for (const [key, value] of Object.entries(en)) assert.equal(names(value), names(key), key)
})
