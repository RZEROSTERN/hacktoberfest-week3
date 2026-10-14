import { MESSAGES } from './messages'

/** The languages PostCall speaks, the same eleven as the interface. */
export const LOCALES = ['en', 'es', 'fr', 'pt', 'ja', 'de', 'ru', 'it', 'hi', 'zh', 'ar'] as const
export type Locale = (typeof LOCALES)[number]

const RIGHT_TO_LEFT: readonly Locale[] = ['ar']

/** `es-MX` -> `es`, `zh-TW` -> `zh`; anything PostCall does not speak is English. */
export function resolveLocale(tag: string | undefined): Locale {
  const main = tag?.toLowerCase().split(/[-_]/)[0]
  return (LOCALES as readonly string[]).includes(main ?? '') ? (main as Locale) : 'en'
}

export function directionOf(locale: Locale): 'ltr' | 'rtl' {
  return RIGHT_TO_LEFT.includes(locale) ? 'rtl' : 'ltr'
}

export function htmlLang(locale: Locale): string {
  return locale === 'zh' ? 'zh-Hans' : locale
}

/** A message in the given language (English when it is missing), with `{values}` filled in. */
export function say(locale: Locale, key: string, values: Record<string, string> = {}): string {
  const text = MESSAGES[locale][key] ?? MESSAGES.en[key] ?? key
  return text.replace(/\{(\w+)\}/g, (_, name: string) => values[name] ?? `{${name}}`)
}
