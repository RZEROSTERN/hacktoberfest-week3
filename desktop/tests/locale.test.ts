import { describe, expect, it } from 'vitest'
import { directionOf, htmlLang, LOCALES, resolveLocale, say } from '../src/locale'
import { MESSAGES } from '../src/messages'
import { startPage } from '../src/startPage'

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1]!).sort()

describe('the languages', () => {
  it('are the same eleven as the interface, in the same order', () => {
    expect([...LOCALES]).toEqual(['en', 'es', 'fr', 'pt', 'ja', 'de', 'ru', 'it', 'hi', 'zh', 'ar'])
  })

  it('pick the system language by its main part and fall back to English', () => {
    expect(resolveLocale('es-MX')).toBe('es')
    expect(resolveLocale('pt_BR')).toBe('pt')
    expect(resolveLocale('zh-TW')).toBe('zh')
    expect(resolveLocale('ko-KR')).toBe('en')
    expect(resolveLocale('')).toBe('en')
    expect(resolveLocale(undefined)).toBe('en')
  })

  it('run right to left only for Arabic', () => {
    expect(LOCALES.filter(l => directionOf(l) === 'rtl')).toEqual(['ar'])
    expect(htmlLang('zh')).toBe('zh-Hans')
  })
})

describe('the messages', () => {
  it.each([...LOCALES])('%s has every message English has, with the same values to fill in', (locale) => {
    const english = MESSAGES.en
    expect(Object.keys(MESSAGES[locale]).sort()).toEqual(Object.keys(english).sort())
    for (const [key, text] of Object.entries(MESSAGES[locale])) {
      expect(text.trim(), `${locale}: ${key}`).not.toBe('')
      expect(placeholders(text), `${locale}: ${key}`).toEqual(placeholders(english[key]!))
    }
  })

  it('fills in values, and falls back to English for a key a language lacks', () => {
    expect(say('en', 'dialog.stopped', { service: 'api' })).toBe('PostCall stopped working (api)')
    expect(say('de', 'dialog.missingParts', { files: 'a, b' })).toContain('a, b')
    expect(say('en', 'no.such.key')).toBe('no.such.key')
  })

  it('keep the product name in every language', () => {
    for (const locale of LOCALES) expect(say(locale, 'splash.title'), locale).toContain('PostCall')
  })
})

describe('the start page', () => {
  it('is written in the language and direction of the system', () => {
    expect(startPage('es')).toContain('lang="es" dir="ltr"')
    expect(startPage('ar')).toContain('lang="ar" dir="rtl"')
    expect(startPage('zh')).toContain('lang="zh-Hans"')
    expect(startPage('de')).toContain(say('de', 'splash.title'))
  })

  it('allows no script and no remote content', () => {
    const page = startPage('en')
    expect(page).toContain("default-src 'none'")
    expect(page).not.toMatch(/<script|https?:\/\//)
  })
})
