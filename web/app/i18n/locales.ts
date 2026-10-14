/** The languages the interface is translated into, in the order the picker shows them. */
export const LOCALES = [
  { code: 'en', name: 'English', htmlLang: 'en', dir: 'ltr' },
  { code: 'es', name: 'Español', htmlLang: 'es', dir: 'ltr' },
  { code: 'fr', name: 'Français', htmlLang: 'fr', dir: 'ltr' },
  { code: 'pt', name: 'Português', htmlLang: 'pt', dir: 'ltr' },
  { code: 'ja', name: '日本語', htmlLang: 'ja', dir: 'ltr' },
  { code: 'de', name: 'Deutsch', htmlLang: 'de', dir: 'ltr' },
  { code: 'ru', name: 'Русский', htmlLang: 'ru', dir: 'ltr' },
  { code: 'it', name: 'Italiano', htmlLang: 'it', dir: 'ltr' },
  { code: 'hi', name: 'हिन्दी', htmlLang: 'hi', dir: 'ltr' },
  // Simplified Chinese: the tag tells the browser which glyph shapes to use.
  { code: 'zh', name: '中文', htmlLang: 'zh-Hans', dir: 'ltr' },
  { code: 'ar', name: 'العربية', htmlLang: 'ar', dir: 'rtl' },
] as const

export type LocaleCode = (typeof LOCALES)[number]['code']

export const DEFAULT_LOCALE: LocaleCode = 'en'

/** Where the chosen language is remembered (a per-person convenience, so browser storage is enough). */
export const LOCALE_STORAGE_KEY = 'postcall.locale'

export function isLocale(code: string | null | undefined): code is LocaleCode {
  return LOCALES.some(l => l.code === code)
}

export function localeInfo(code: LocaleCode) {
  return LOCALES.find(l => l.code === code) ?? LOCALES[0]
}

/**
 * The first of the preferred languages (in order, as a browser lists them) that the app speaks.
 * Only the main part of a tag counts: `pt-BR` and `pt-PT` are Portuguese, `zh-TW` and `zh-CN` are the one
 * Chinese we have, `en-GB` is English. Nothing matching means English.
 */
export function resolveLocale(preferred: readonly (string | null | undefined)[]): LocaleCode {
  for (const tag of preferred) {
    const main = tag?.toLowerCase().split(/[-_]/)[0]
    if (isLocale(main)) return main
  }
  return DEFAULT_LOCALE
}
