import { describe, expect, it } from 'vitest'
import { formatDuration, languageName, withUnit } from '../app/utils/intl'

describe('formatDuration', () => {
  it('writes minutes and seconds with the language\'s own abbreviations', () => {
    expect(formatDuration(323.9, 'en')).toBe('5 min 24 sec')
    expect(formatDuration(40, 'en')).toBe('40 sec')
    expect(formatDuration(null, 'en')).toBe('')
    expect(formatDuration(323.9, 'de')).toMatch(/^5 Min\.? 24 Sek\.?$/)
    expect(formatDuration(323.9, 'ja')).toMatch(/5.*24/)
  })
})

describe('withUnit', () => {
  it('keeps the number and the unit together in every language', () => {
    for (const locale of ['en', 'es', 'fr', 'pt', 'ja', 'de', 'ru', 'it', 'hi', 'zh', 'ar']) {
      expect(withUnit(574, 'megabyte', locale), locale).toMatch(/574|٥٧٤|५७४/)
    }
  })
})

describe('languageName', () => {
  it('names a language in the language of the interface, with a capital first letter', () => {
    expect(languageName('es', 'en')).toBe('Spanish')
    expect(languageName('es', 'fr')).toBe('Espagnol')
    expect(languageName('en', 'es')).toBe('Inglés')
    expect(languageName('ja', 'de')).toBe('Japanisch')
    expect(languageName('zh', 'ru')).toBe('Китайский')
  })

  it('has nothing to say about no language, and passes an unknown code through', () => {
    expect(languageName(null, 'en')).toBe('')
    expect(languageName('zzz', 'en')).toMatch(/zzz/i)
  })
})
