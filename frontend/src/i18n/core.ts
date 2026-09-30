/**
 * Translation without any framework: the Korean text is the key.
 *
 * Korean is what the screens were written in, so `t('질문하기')` returns its own
 * argument in Korean and looks the English text up otherwise. A missing English
 * entry falls back to the Korean text rather than showing nothing, and a test
 * checks that every literal key used in the source has an entry.
 *
 * Values go in with {name} placeholders: t('{n}건을 삭제했습니다', { n: 3 }).
 */

export type Locale = 'ko' | 'en'
export type Params = Record<string, string | number>
export type Catalog = Record<string, string>

export function fill(text: string, params?: Params): string {
  if (!params) return text
  return text.replace(/\{(\w+)\}/g, (whole, name) => (name in params ? String(params[name]) : whole))
}

export function translate(locale: Locale, catalog: Catalog, key: string, params?: Params): string {
  const text = locale === 'en' ? catalog[key] ?? key : key
  return fill(text, params)
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/**
 * Like translate, for text shown with v-html: the sentence may carry its own
 * markup (<b>, <em>, <code>), but every value filled into it is escaped, so
 * a name or a message from the server can never inject markup.
 */
export function translateHtml(locale: Locale, catalog: Catalog, key: string, params?: Params): string {
  const safe = params
    ? Object.fromEntries(Object.entries(params).map(([k, v]) => [k, escapeHtml(String(v))]))
    : undefined
  return translate(locale, catalog, key, safe)
}

/** The language a stored value names; anything else is Korean. */
export function parseLocale(value: unknown): Locale {
  return value === 'en' ? 'en' : 'ko'
}
