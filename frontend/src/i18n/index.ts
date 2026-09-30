/**
 * The language of the screens: Korean (the default) or English.
 *
 * The choice is remembered in this browser. `t` reads the reactive `locale`, so
 * anything rendered through it redraws when the language is switched.
 */
import { ref } from 'vue'
import { parseLocale, translate, translateHtml, type Locale, type Params } from './core'
import { en } from './en'

const STORAGE_KEY = 'kfms.locale'

function stored(): Locale {
  try {
    return parseLocale(localStorage.getItem(STORAGE_KEY))
  } catch {
    return 'ko' // storage can be unavailable (private windows, blocked site data)
  }
}

export const locale = ref<Locale>(stored())

function applyToPage(value: Locale) {
  if (typeof document !== 'undefined') document.documentElement.lang = value
}
applyToPage(locale.value)

export function setLocale(next: Locale) {
  locale.value = next
  applyToPage(next)
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // The choice then lasts until the page is closed.
  }
}

const ROLE_NAMES: Record<string, { ko: string; en: string }> = {
  admin: { ko: '관리자', en: 'Administrator' },
  auditor: { ko: '감사담당', en: 'Auditor' },
  viewer: { ko: '조회', en: 'Viewer' }, // "조회" alone is a button ("Search"); as a role it is a viewer
}

/** The name of a role in the current language. */
export function roleName(role: string | null | undefined): string {
  const names = ROLE_NAMES[role || '']
  return names ? names[locale.value] : ''
}

/** Text in the current language. The Korean text itself is the key. */
export function t(key: string, params?: Params): string {
  return translate(locale.value, en, key, params)
}

/** Text with its own markup, for v-html. Values filled in are escaped. */
export function th(key: string, params?: Params): string {
  return translateHtml(locale.value, en, key, params)
}

/** A date and time in the format of the chosen language. */
export function formatDateTime(value: string | number | Date): string {
  return new Date(value).toLocaleString(locale.value === 'en' ? 'en-US' : 'ko-KR')
}

declare module 'vue' {
  interface ComponentCustomProperties {
    $t: typeof t
    $th: typeof th
  }
}
